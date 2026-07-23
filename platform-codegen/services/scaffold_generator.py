import hashlib
import json
import re
from pathlib import Path
from infrastructure.cache import cache_client
from infrastructure.logger import log
from infrastructure.storage import storage_client
from config.settings import settings
from services.llm import llm_client
from services.sanitizer import sanitizer
from services.validators import (
    DesignOutput,
    SkeletonOutput,
    SkeletonPatchOutput,
    FunctionDeltaOutput,
    JudgeQAOutput,
    validate_with_correction,
)
from generator.engine import generator
from services.few_shot_loader import load_few_shot_repos
from services.compile_validator import compile_validator, CompileValidationError

_JAVA_POM_TEMPLATE = (
    Path(__file__).parent.parent / "templates" / "java" / "pom.xml"
).read_text(encoding="utf-8")

_JAVA_APP_TEMPLATE = (
    Path(__file__).parent.parent / "templates" / "java" / "ChallengeApplication.java"
).read_text(encoding="utf-8")

_SUPPORTED_LANGUAGES = {"node", "java", "python"}
_TIERS = ("easy", "medium", "hard")

# Fixed topic taxonomy for scenario classification (Phase 1 design assigns one per scenario;
# Phase 4 judge QA verifies the assignment matches what the scenario actually exercises).
# Starting list — extend as new challenge domains require topics not covered here.
_TOPICS = (
    "concurrency",
    "caching",
    "pagination",
    "auth-authz",
    "data-modeling",
    "idempotency",
    "rate-limiting",
    "consistency",
    "resilience",
    "search-filtering",
    "notifications",
    "payments",
)

_MAX_QA_RETRIES = 2

_REQUIRED_TEST_CATEGORIES = {
    "easy": (
        "Happy path", "Not found", "Forbidden", "Validation",
        "Boundary values", "State consistency", "Idempotency",
    ),
    "medium": (
        "Happy path", "Not found", "Forbidden", "Validation",
        "Boundary values", "State consistency", "Idempotency",
        "Partial data", "Type edge cases",
    ),
    "hard": (
        "Happy path", "Not found", "Forbidden", "Validation",
        "Boundary values", "State consistency", "Idempotency",
        "Partial data", "Type edge cases",
        "Concurrency hints", "Infrastructure state", "Cascading failures",
    ),
}


def _select_delta_prompt_name(language: str, scenario_type: str, check_mode: str) -> str:
    """Phase 2b prompt selection. check_mode is orthogonal to scenario_type (implement/debug)
    — a debug scenario can still be judge-graded. judge_function_{lang} handles both implement
    and debug intent itself (via strip_description/bug_description), mirroring how
    implement_function_{lang}/debug_function_{lang} already split.
    """
    if check_mode == "non_deterministic":
        return f"judge_function_{language}"
    if scenario_type == "debug":
        return f"debug_function_{language}"
    return f"implement_function_{language}"


def _test_file_path(java_source: str) -> str | None:
    pkg = re.search(r"^\s*package\s+([\w.]+)\s*;", java_source, re.MULTILINE)
    cls = re.search(r"\bpublic\s+class\s+(\w+)", java_source)
    if not pkg or not cls:
        return None
    return f"src/test/java/{pkg.group(1).replace('.', '/')}/{cls.group(1)}.java"


_JUNIT_METHOD_FAILURE_RE = re.compile(
    r"\[ERROR\]\s+[\w.$]+\.(\w+)\s+--\s+Time elapsed:.*?<<<\s*(?:FAILURE|ERROR)!"
)


def _is_only_stub_related_test_failure(error_output: str) -> bool:
    """True only if EVERY failing/erroring JUnit test method in a `run_tests=True`
    validation failure is attributable to a scenario's own not-yet-implemented target
    stub — `throw new UnsupportedOperationException("not implemented: {scenario_tag}");`,
    the fixed, exact string every `implement`-type stub must use per
    `prompts/implement_skeleton_java.mdx`.

    Used ONLY at the Phase 2a skeleton-validation stage, where the skeleton's own
    required starter test (`implement_skeleton_java.mdx`'s "at least one fully
    implemented test file") can coincidentally exercise a scenario's target-stub method,
    which is *expected* to throw at this point — that's not a bug, it's the stub format
    working as designed, and should NOT burn a retry attempt or confuse the LLM into
    trying to "fix" a stub that's supposed to stay a stub until Phase 2b.

    Finds every per-method JUnit failure header (`[ERROR] <FQCN>.<method> -- Time
    elapsed: ... <<< FAILURE!/ERROR!`) and checks the text up to the NEXT such header (or
    end of output) for the stub marker substring. If ANY failing method's own segment
    lacks it, or no recognizable per-method failure header is found at all (a plain
    compile error looks nothing like this, for instance), this conservatively returns
    False — bail rather than guess, consistent with every other helper in this file. Does
    NOT attempt to detect `debug`-type scenario collisions (a deliberately-broken, non-
    throwing method coincidentally exercised by the same starter test) — no reliable
    textual signal ties a plain assertion mismatch back to which method produced it, and
    that residual risk is bounded by the ordinary skeleton-retry ceiling regardless.
    """
    matches = list(_JUNIT_METHOD_FAILURE_RE.finditer(error_output))
    if not matches:
        return False
    for i, match in enumerate(matches):
        segment_end = matches[i + 1].start() if i + 1 < len(matches) else len(error_output)
        segment = error_output[match.end():segment_end]
        if "not implemented:" not in segment:
            return False
    return True


def _is_test_execution_failure(error_output: str) -> bool:
    """True if a `run_tests=True` validation failed during test EXECUTION, not
    compilation — the code compiled fine, a test's behavior just didn't match.

    Used only to decide whether it's safe to fall back to a compile-only acceptance of
    the skeleton once the retry budget is exhausted: a genuine compile error must still
    hard-fail the pipeline (unchanged, non-negotiable), but a persisting test-only
    failure should degrade no worse than the pre-existing behavior from before Phase 2a
    started executing its own tests at all (skeleton compiles → proceed), rather than
    turning a bug the pipeline previously would have silently deferred to gold master
    into a hard failure here instead.
    """
    if "COMPILATION ERROR" in error_output:
        return False
    return "<<< FAILURE!" in error_output or "<<< ERROR!" in error_output


def _classify_compile_error(error_output: str, delta_phase: bool = False) -> str:
    # A single `mvn` run frequently reports SEVERAL distinct, unrelated error categories
    # at once (e.g. a bad import path AND a duplicate class definition in the same
    # output). Treating these as mutually exclusive "first match wins" branches means
    # the LLM's one regeneration attempt only ever hears about whichever category
    # happened to be checked first — it silently never learns about the others, fixes
    # only part of the problem, and re-fails. Accumulate a hint per detected category
    # and return them all together instead.
    hints: list[str] = []

    if "does not exist" in error_output and "com.challenge" in error_output:
        if delta_phase:
            hints.append(
                "An import references a `com.challenge.*` package that doesn't exist. "
                "In this phase you cannot add new files — you can only return `function_body` "
                "and `imports`. If the class IS listed in <skeleton_classes> (just not yet "
                "imported into <stub_file_content>), add the correct `import ...;` line to "
                "the `imports` array — do not avoid using it. If it is NOT in "
                "<skeleton_classes> at all, it doesn't exist; rewrite the function body to "
                "only use classes actually listed there."
            )
        else:
            hints.append(
                "An import references a `com.challenge.*` package that doesn't exist. "
                "There are two distinct causes here — check which applies before acting: "
                "(1) the class is genuinely missing — add its file to your `files` output; "
                "every 'import com.challenge.X' must have a corresponding generated file. "
                "(2) the class already EXISTS elsewhere in your own `files` output (often "
                "in the SAME package as the importing file, or a different sub-package "
                "than the one you guessed) — in that case do NOT generate a duplicate "
                "file, just fix the import to the class's real package (or delete the "
                "import entirely if it's in the same package as the importing file — "
                "classes in the same package need no import at all)."
            )

    if "is already defined in this compilation unit" in error_output:
        hints.append(
            "A class is declared more than once with the same fully-qualified name — "
            "either duplicated inside a single file, or the same class generated under "
            "two different filenames in the same package. Find the duplicate declaration "
            "and remove it, keeping exactly one definition of that class in your `files` "
            "output."
        )

    if "cannot find symbol" in error_output:
        # Maven right-pads "symbol:" with extra spaces so its value column-aligns with
        # "location:" below it (e.g. "symbol:   method foo()" vs "location: class Bar").
        # A plain ": method"/": class"/": variable" substring check breaks on that padding
        # and ends up accidentally matching the unrelated "location:" line instead — so
        # anchor explicitly to the "symbol:" line's kind token, tolerant of any spacing.
        #
        # A single compiler run often reports SEVERAL distinct "cannot find symbol" errors
        # of DIFFERENT kinds at once (e.g. a missing class AND an undeclared field in the
        # same file). Using re.search here would only ever see the first one and silently
        # drop guidance for the rest, so the LLM's regeneration attempt would only fix part
        # of the problem and re-fail. Collect every distinct kind present and compose a
        # hint that addresses all of them.
        symbol_kinds = set(re.findall(r"symbol:\s*(method|class|variable)\b", error_output))

        symbol_hints: list[str] = []

        if "method" in symbol_kinds:
            if delta_phase:
                symbol_hints.append(
                    "You called a method that doesn't exist. Two distinct causes: "
                    "(1) You invented a helper method on `this` that isn't actually defined — "
                    "check <stub_file_content> for the real methods available and implement the "
                    "logic inline instead. (2) You called a getter/setter on a DIFFERENT class "
                    "(not the one in <stub_file_content>) that doesn't have that field — in THIS "
                    "phase you cannot edit that other class's file at all, so restructure your "
                    "logic to only use fields/methods that class already exposes (check "
                    "<skeleton_classes>) rather than assuming a field it doesn't have."
                )
            else:
                symbol_hints.append(
                    "You called a method that doesn't exist on a class you generated in this "
                    "same skeleton — most often a missing getter/setter, or a helper method you "
                    "referenced but never defined. Check every class in your own `files` output: "
                    "any class with private fields must have real Lombok `@Getter`/`@Setter` "
                    "annotations or fully written accessor methods, never a `// Getters and "
                    "setters...` placeholder; any helper method you call on `this` must actually "
                    "be defined in that same class, not just invented. Add the missing method to "
                    "that class's file, or fix the caller to match what the class actually provides."
                )

        # "location: class com.challenge...." (dot form) is only present when javac has
        # a location to report; some "class" cannot-find-symbol errors (e.g. a bare type
        # argument like `JpaRepository<Book, UUID>`) omit the location line entirely, so
        # this must also match the slash form javac uses in the file path itself
        # ("/tmp/.../src/main/java/com/challenge/...") to still catch those.
        if "class" in symbol_kinds:
            if delta_phase:
                symbol_hints.append(
                    "You referenced a class that isn't imported (or doesn't exist) "
                    "in this file. If it is a framework/standard class (like Spring's @Autowired or java.util.UUID), "
                    "you MUST add the correct `import ...;` line to the `imports` array. "
                    "If it is a project class, check <skeleton_classes> for the exact class names "
                    "available: if it's listed there, add the import; if it isn't listed there, it doesn't exist — do not invent it."
                )
            else:
                symbol_hints.append(
                    "You referenced a class that isn't imported (or doesn't exist). "
                    "If it is a framework or standard library class (like Spring's @Autowired, @Service, or java.util.List), "
                    "you MUST add the correct `import` statement at the top of the file! "
                    "If it is a project class, check <skeleton_classes> for the exact class names available, and add the "
                    "missing class file to your `files` output if it is genuinely missing. Only reference project classes listed there."
                )

        if "variable" in symbol_kinds:
            # Java reports "cannot find symbol: variable Foo" in (at least) two distinct
            # situations, and the fix differs for each:
            #   1. Foo is actually a class name used as a type (return type, parameter,
            #      local variable) whose .java file was never generated.
            #   2. Foo is an instance field (e.g. a repository/service) that the class
            #      references but never declares — most often a helper/validator class
            #      that uses a repository without declaring it as a constructor-injected
            #      field.
            # Since the error message alone doesn't disambiguate, give guidance for both.
            if delta_phase:
                symbol_hints.append(
                    "You referenced something ('cannot find symbol: variable ...') that "
                    "isn't resolving. This has two distinct causes — check which applies: "
                    "(a) you used a class that IS listed in <skeleton_classes> but isn't "
                    "imported into <stub_file_content> yet — add the correct `import ...;` "
                    "line to the `imports` array (do NOT avoid using the class, and do NOT "
                    "inline a fully-qualified name instead); (b) you referenced a field "
                    "(e.g. a repository or service) that the stub class genuinely never "
                    "declares — add it to the `fields` array as a plain declaration (e.g. "
                    "`\"private ReservationRepository reservationRepository;\"`, no "
                    "`@Autowired` needed, it's added automatically) instead of avoiding the "
                    "dependency or inventing a workaround."
                )
            else:
                symbol_hints.append(
                    "Something referenced in your code was never declared. This javac error "
                    "('cannot find symbol: variable X') covers two distinct causes — check "
                    "for both: (1) X is a class used as a type (return type, parameter, local "
                    "variable) whose .java file was never generated — add the missing class "
                    "file to your `files` output; (2) X is an instance field (commonly a "
                    "repository or service, e.g. `pieceRepository`) that the class uses but "
                    "never declares — add the missing `private final X x;` field and wire it "
                    "through the class's constructor, the same way other classes in this "
                    "skeleton inject their repositories/services."
                )

        if symbol_hints:
            hints.extend(symbol_hints)
        elif delta_phase:
            hints.append(
                "You used a class without importing it. `function_body` cannot change the "
                "file's import section — add the missing import (e.g. `import java.util.Optional;`, "
                "`import java.time.LocalDate;`, `import java.util.UUID;`) to the `imports` array instead."
            )
        else:
            hints.append(
                "You used a class without importing it. "
                "Add the missing import at the top of the file "
                "(e.g. `import java.util.Optional;`, `import java.time.LocalDate;`, `import java.util.UUID;`)."
            )

    if "illegal start of expression" in error_output or "not a statement" in error_output:
        hints.append(
            "Your code has a syntax error. "
            "Check for unclosed braces, misplaced keywords, or incomplete statements."
        )

    if "cannot be applied to given types" in error_output:
        hints.append(
            "You called a constructor or method with the wrong number or type of "
            "arguments. Check the ACTUAL declared signature of that constructor/method "
            "(its parameter list, in order) wherever it's defined, and pass arguments "
            "that match it exactly — do not guess the signature or assume a no-arg "
            "constructor exists."
        )

    if "incompatible types" in error_output:
        hints.append(
            "You returned or assigned a value whose type doesn't match what's declared "
            "(e.g. a method declared to return one type is returning something else, "
            "such as a raw String instead of the proper object/DTO type). Check the "
            "declared return/variable type at that exact location and construct/return "
            "a value of that exact type instead."
        )

    if "must be caught or declared to be thrown" in error_output:
        if delta_phase:
            hints.append(
                "You're throwing/calling something that throws a CHECKED exception "
                "(a class extending `Exception`, not `RuntimeException`) without catching "
                "it — and in this phase you cannot add a `throws` clause to the method "
                "signature (`function_body` only replaces the method body). Check whether "
                "other custom exceptions in this skeleton extend `RuntimeException` "
                "instead (unchecked exceptions never need this) — if so, that's very "
                "likely the pattern to follow here too. Otherwise, wrap the call in a "
                "try/catch inside the method body instead of letting the checked "
                "exception propagate unhandled."
            )
        else:
            hints.append(
                "You're throwing/calling something that throws a CHECKED exception (a "
                "class extending `Exception`, not `RuntimeException`) without catching it "
                "or declaring `throws` on the calling method. Check how OTHER custom "
                "exceptions in this skeleton are declared — they almost certainly extend "
                "`RuntimeException`, which never requires this. Make this exception class "
                "consistent with that pattern (extend `RuntimeException`) rather than "
                "adding `throws` clauses everywhere it's used."
            )

    # Reachable at any run_tests=True stage — the gold-master stage, and (since the
    # skeleton's own required starter test is now executed too, not just compiled) the
    # Phase 2a skeleton-validation stage as well; never delta_phase, whose compile checks
    # only ever run test-compile. This is a JUnit assertion failure, not a compile error:
    # the implementation ran fine but produced a value the test didn't expect.
    if not delta_phase and (
        "AssertionFailedError" in error_output
        or re.search(r"expected:\s*<.*?>\s*but was:\s*<.*?>", error_output)
    ):
        hints.append(
            "A test's assertion failed — this is NOT a compile error, the code ran "
            "but produced a value the test didn't expect. Do NOT simply change the test's "
            "expected value to match whatever the implementation currently outputs — that "
            "papers over a real bug instead of fixing it. Re-derive the correct expected "
            "value directly from the stated business rules (caps, minimums/maximums, "
            "rounding, boundary conditions) and fix whichever side — the implementation or "
            "the test — doesn't match that derivation. If other tests in the same file "
            "already correctly apply the same rule, a newly-failing test that contradicts "
            "them is a strong signal the TEST is the one that's wrong, not the "
            "implementation. If this is the skeleton's own required starter test, also "
            "check for a conflict between it and your OWN Flyway seed data (e.g. a "
            "hardcoded ID the test assumes is 'fresh' that your seed migration already "
            "used for the same relationship) — fix whichever one doesn't match the other."
        )

    # "<<< ERROR!" (vs "<<< FAILURE!") is JUnit/surefire's marker for a test that threw an
    # uncaught exception while running, as opposed to an assertion that merely didn't
    # match — reachable at any run_tests=True stage (see above).
    if not delta_phase and "<<< ERROR!" in error_output:
        hints.append(
            "A test threw an unexpected exception while running — this isn't an "
            "assertion mismatch, the code crashed. Read the stack trace to find the exact "
            "line in your OWN code (com.challenge.*) where it crashed and what caused it "
            "(e.g. a NullPointerException usually means a field/parameter you assumed was "
            "set was actually null — check for a missing null check, a required argument "
            "the test didn't pass, or a lookup/enum value that doesn't match). Fix the "
            "root cause at that exact location, not just the symptom."
        )

    if hints:
        return "\n\n".join(hints)

    return "Fix the compilation error shown above before returning the corrected JSON."


def _skeleton_classes_summary(skeleton_files: dict[str, str]) -> str:
    fqns = sorted(
        m.group(1).replace("/", ".")
        for path in skeleton_files
        if (m := re.search(r"src/main/java/(.+)\.java$", path))
    )
    if not fqns:
        return ""
    lines = ["Available classes in this skeleton (ONLY reference these — do not invent class names):"]
    lines += [f"  - {fqn}" for fqn in fqns]
    return "\n".join(lines)


_JAVA_IMPORT_RE = re.compile(r"^import (com\.challenge\.[\w.]+);$", re.MULTILINE)
_JAVA_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_JAVA_PUBLIC_TYPE_RE = re.compile(r"\bpublic\s+(?:final\s+|abstract\s+)?(?:class|interface|enum|record)\s+(\w+)")


def _fix_java_source_paths(files: dict[str, str]) -> dict[str, str]:
    """Relocate `.java` files the LLM placed outside Maven's source roots to their
    correct path, derived from the file's own `package` declaration and public type
    name — regardless of what path key the LLM emitted the file under.

    Maven only compiles sources actually found under `src/main/java` (tests under
    `src/test/java`); a file emitted at some other path (e.g. a flat `src/foo/Bar.java`,
    which the model occasionally produces for Java skeletons — plausibly bleeding in a
    Node-style flat `src/` convention) is silently invisible to the build. Anything that
    references it then fails with 'package ... does not exist' even though the class
    technically exists in the skeleton output. This must run before `_fix_java_imports`,
    since that function derives its class-location map from these same canonical paths.
    """
    fixed: dict[str, str] = {}
    for path, content in files.items():
        if not path.endswith(".java") or re.match(r"^src/(main|test)/java/", path):
            fixed[path] = content
            continue

        pkg_match = _JAVA_PACKAGE_RE.search(content)
        type_match = _JAVA_PUBLIC_TYPE_RE.search(content)
        if not pkg_match or not type_match:
            fixed[path] = content  # can't safely determine the correct path — leave as-is
            continue

        new_path = f"src/main/java/{pkg_match.group(1).replace('.', '/')}/{type_match.group(1)}.java"
        if new_path in files or new_path in fixed:
            fixed[path] = content  # extremely unlikely collision — don't clobber
            continue
        fixed[new_path] = content

    return fixed


# Fixed fact table: common JDK classes these skeletons routinely use bare without
# importing. Never inferred or guessed — a static mapping, purely a Java-standard-library
# convention (same governing principle as every other deterministic fix here).
_JAVA_JDK_IMPORTS: dict[str, str] = {
    "List": "java.util.List",
    "ArrayList": "java.util.ArrayList",
    "Map": "java.util.Map",
    "HashMap": "java.util.HashMap",
    "Set": "java.util.Set",
    "HashSet": "java.util.HashSet",
    "Optional": "java.util.Optional",
    "UUID": "java.util.UUID",
    "LocalDate": "java.time.LocalDate",
    "LocalDateTime": "java.time.LocalDateTime",
    "LocalTime": "java.time.LocalTime",
    "Duration": "java.time.Duration",
    "Instant": "java.time.Instant",
    "BigDecimal": "java.math.BigDecimal",
    "BigInteger": "java.math.BigInteger",
    "Collectors": "java.util.stream.Collectors",
    "Comparator": "java.util.Comparator",
    "Collections": "java.util.Collections",
}


_JAVA_TOP_LEVEL_TYPE_RE = re.compile(
    r"^(public\s+)?(?:final\s+|abstract\s+)?(?:class|interface|enum|record)\s+(\w+)",
    re.MULTILINE,
)


def _fix_java_imports(files: dict[str, str]) -> dict[str, str]:
    """Deterministically correct `com.challenge.*` imports that guess the wrong
    sub-package for a class that already exists elsewhere in the skeleton, and add
    imports that were never written at all for a class used bare.

    Producing an entire multi-file Java codebase in one LLM completion reliably hits
    two variants of the same self-consistency mistake, regardless of business domain:
    (1) it writes `import com.challenge.<guessed-subpackage>.Foo;` for a class `Foo` it
    did generate, just under a different package than it imported from — the rewrite
    pass below fixes this; (2) it references a cross-package class with NO import
    statement at all — most often a JPA repository's generic type argument, e.g.
    `JpaRepository<Book, Long>` where `Book` lives in a different package — which the
    rewrite pass can't touch since there's no existing import line to correct. The
    second pass below handles that: for every unambiguous skeleton class, if its simple
    name appears as a whole word in another file that doesn't already import it and
    isn't in the same package, add the import.

    A class is registered by scanning EVERY top-level type declaration in each file's
    content, not just the one matching the file's own name — the model sometimes emits
    a secondary top-level type in the same file (most often a JPA `@Embeddable` composite
    key alongside its owning `@Entity`, e.g. `class StockLevelId` declared in
    `StockLevel.java`). A class registered only by filename would miss that secondary
    type entirely, silently leaving it un-importable from any other package.

    Classes that don't exist anywhere in the skeleton are left untouched — that's a
    genuinely missing file, which the existing compile-validate retry loop still
    catches and asks the LLM to add.
    """
    class_to_fqcn: dict[str, str | None] = {}
    # simple_name -> (defining file path, is declared `public`) — None once a name is
    # seen in more than one place (ambiguous, never guess); used below to fix
    # cross-package visibility on secondary top-level types.
    class_decl_info: dict[str, tuple[str, bool] | None] = {}

    def _register(simple_name: str, path: str, own_package: str, is_public: bool) -> None:
        fqcn = f"{own_package}.{simple_name}" if own_package else simple_name
        if simple_name in class_to_fqcn:
            class_to_fqcn[simple_name] = None
            class_decl_info[simple_name] = None
        else:
            class_to_fqcn[simple_name] = fqcn
            class_decl_info[simple_name] = (path, is_public)

    for path, content in files.items():
        m = re.search(r"src/main/java/(.+)\.java$", path)
        if not m:
            continue
        fqcn_parts = m.group(1).replace("/", ".")
        own_package = fqcn_parts.rsplit(".", 1)[0] if "." in fqcn_parts else ""
        primary_name = fqcn_parts.rsplit(".", 1)[-1]

        found_primary = False
        for type_match in _JAVA_TOP_LEVEL_TYPE_RE.finditer(content):
            is_public, simple_name = bool(type_match.group(1)), type_match.group(2)
            if simple_name == primary_name:
                found_primary = True
                is_public = True  # the file's own public type, by Maven/javac convention
            _register(simple_name, path, own_package, is_public)
        # Fallback: filename-derived primary class even if the regex above (which
        # requires the declaration to start at column 0) didn't match it for some
        # reason — keeps prior behaviour as a floor.
        if not found_primary:
            _register(primary_name, path, own_package, True)

    def _rewrite_for(own_package: str):
        def _rewrite(match: re.Match) -> str:
            imported_fqcn = match.group(1)
            simple_name = imported_fqcn.rsplit(".", 1)[-1]
            actual_fqcn = class_to_fqcn.get(simple_name)
            if not actual_fqcn or actual_fqcn == imported_fqcn:
                return match.group(0)
            actual_package = actual_fqcn.rsplit(".", 1)[0]
            if actual_package == own_package:
                return ""  # same package as the importing file — no import needed
            return f"import {actual_fqcn};"
        return _rewrite

    fixed: dict[str, str] = {}
    own_packages: dict[str, str] = {}
    for path, content in files.items():
        # Test files (src/test/java/...) can have the exact same wrong-subpackage import
        # mistake as main sources — must be covered too, not just src/main/java/.
        m = re.search(r"src/(?:main|test)/java/(.+)\.java$", path)
        if not m:
            fixed[path] = content
            continue
        own_package = m.group(1).replace("/", ".").rsplit(".", 1)[0]
        own_packages[path] = own_package
        fixed[path] = _JAVA_IMPORT_RE.sub(_rewrite_for(own_package), content)

    # Second pass: add imports that were never written at all (see docstring, case 2).
    # Also covers common JDK classes (a fixed, static fact table — not a guess) alongside
    # skeleton classes, so a bare `List`/`Optional`/`UUID` etc. left unimported doesn't
    # have to burn an LLM round trip just to add one well-known standard-library import.
    project_known = {k: v for k, v in class_to_fqcn.items() if v}
    all_known_names = {**_JAVA_JDK_IMPORTS, **project_known}
    for path, own_package in own_packages.items():
        content = fixed[path]
        for simple_name, actual_fqcn in all_known_names.items():
            if not actual_fqcn:
                continue
            actual_package = actual_fqcn.rsplit(".", 1)[0]
            if actual_package == own_package:
                continue  # same package (or this file's own class) — no import needed
            if re.search(rf"^import\s+{re.escape(actual_fqcn)}\s*;", content, re.MULTILINE):
                continue  # already correctly imported
            if not re.search(rf"\b{re.escape(simple_name)}\b", content):
                continue  # not referenced in this file at all
            # If some OTHER package already provides a class with this same simple name
            # in this file (e.g. a skeleton class happens to share a name with a JDK type
            # like `Optional`), adding our own import would create an ambiguous/competing
            # import rather than fix anything — leave it alone.
            if re.search(rf"^import\s+(?!com\.challenge\.)[\w.]*\.{re.escape(simple_name)}\s*;", content, re.MULTILINE):
                continue
            content = _insert_imports(content, [actual_fqcn])
        fixed[path] = content

    # Third pass: a secondary top-level type (registered above but declared without
    # `public`, e.g. a JPA `@Embeddable` composite key sharing a file with its owning
    # `@Entity`) compiles fine as long as it's only ever used within its own package.
    # The moment ANY other file references it by name — which the import passes above
    # just confirmed by adding an import, or it was already imported — default
    # (package-private) visibility makes it inaccessible and javac reports "is not
    # public in X; cannot be accessed from outside package". Simply adding `public` in
    # place is NOT enough and actively breaks the build a different way: javac requires
    # every `public` top-level type to live in its own file named after it, and the
    # *first* type in the file (the one the file is already named for) is already
    # public — so the secondary type must be split out into its own file, not just have
    # a modifier flipped. There's no judgment call in any of this: both rules are fixed
    # javac requirements, not a guess about the code's meaning.
    for path, own_package in list(own_packages.items()):
        content = fixed[path]
        for simple_name, decl in list(class_decl_info.items()):
            if decl is None:
                continue  # ambiguous declaration site — don't guess
            def_path, is_public = decl
            if is_public or def_path == path:
                continue
            actual_fqcn = class_to_fqcn.get(simple_name)
            if not actual_fqcn or actual_fqcn.rsplit(".", 1)[0] == own_package:
                continue  # same package — default visibility already sufficient
            if not re.search(rf"\b{re.escape(simple_name)}\b", content):
                continue  # not referenced from this other-package file
            def_content = fixed.get(def_path)
            if def_content is None:
                continue
            extracted = _extract_secondary_type_to_own_file(def_content, simple_name, own_package_of(def_path))
            if extracted is None:
                continue  # couldn't safely locate/extract — leave for the LLM
            new_path, new_content, remaining_content = extracted
            if new_path in fixed:
                continue  # extremely unlikely collision — don't clobber
            fixed[def_path] = remaining_content
            fixed[new_path] = new_content
            class_decl_info[simple_name] = (new_path, True)  # only needs doing once

    return fixed


def own_package_of(path: str) -> str:
    m = re.search(r"src/(?:main|test)/java/(.+)\.java$", path)
    fqcn_parts = m.group(1).replace("/", ".") if m else ""
    return fqcn_parts.rsplit(".", 1)[0] if "." in fqcn_parts else ""


def _find_matching_close_brace(content: str, open_brace_idx: int) -> int:
    """Return the index of the `}` that closes the `{` at `open_brace_idx`, by simple
    depth counting. Doesn't account for braces inside string/char literals or comments —
    an accepted best-effort heuristic consistent with the rest of this module's
    regex-based Java handling (no real AST available), fine for the generated,
    mechanically-shaped entity/DTO files this targets.
    """
    depth = 0
    for i in range(open_brace_idx, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


_JAVA_OMITTED_BODY = " /* implementation omitted for context */ "


def _strip_java_member_bodies(class_body: str) -> str:
    """Replace every top-level member body (method, constructor, static/instance
    initializer block, or nested type) inside a class/interface body with a fixed
    placeholder, keeping everything else — annotations, modifiers, return types, method
    names, parameter lists, `throws` clauses, and field declarations — untouched.

    Scans `class_body` (the text strictly BETWEEN a type's outer `{` and `}`) at its own
    top level only: every `;` at that level ends a field/statement (kept as-is); every
    `{` at that level opens a member body, whose matching `}` is found via
    `_find_matching_close_brace` and whose entire interior — including any further
    nesting inside it (control flow, lambdas, anonymous classes) — is replaced in one
    shot. This deliberately does NOT try to distinguish a method body from a nested
    type's body (e.g. a private inner `class Builder { ... }`) — both get elided the
    same way, which is an accepted limitation (nested types lose their own field/method
    visibility in this summary) rather than a correctness risk, since this output is
    only ever used as LLM prompt context, never compiled.

    One known cosmetic edge case: an annotation using array-literal syntax with braces
    (e.g. `@SuppressWarnings({"unchecked"})`) also contains a top-level `{...}` and gets
    replaced the same way — harmless for context purposes, and not observed in this
    codebase's generated skeletons.
    """
    pieces = []
    depth0_start = 0
    i = 0
    n = len(class_body)
    while i < n:
        c = class_body[i]
        if c == ";":
            pieces.append(class_body[depth0_start:i + 1])
            i += 1
            depth0_start = i
            continue
        if c == "{":
            close_idx = _find_matching_close_brace(class_body, i)
            if close_idx == -1:
                pieces.append(class_body[depth0_start:])
                return "".join(pieces)
            pieces.append(class_body[depth0_start:i + 1])
            pieces.append(_JAVA_OMITTED_BODY)
            pieces.append("}")
            i = close_idx + 1
            depth0_start = i
            continue
        i += 1
    pieces.append(class_body[depth0_start:])
    return "".join(pieces)


def _java_signature_summary(files: dict[str, str], keep_full: frozenset[str] = frozenset()) -> dict[str, str]:
    """Build a token-cheap version of a Java file set for LLM prompt context: every file
    keeps its package, imports, class/interface-level annotations, type declaration,
    and field declarations exactly as-is, but every method/constructor BODY is replaced
    with a fixed placeholder — the model still sees every available method's exact
    signature (preventing it from inventing one that doesn't exist), just not the
    implementation detail of methods it isn't editing right now.

    `README*.md` and `pom.xml` are dropped entirely — never needed to implement a
    method. Any path in `keep_full` (typically the one file actually being edited, which
    the caller already sends in full elsewhere) passes through completely unmodified.

    Built to cut prompt size at the three places that otherwise dump entire skeletons
    (or the full assembled gold master) verbatim into every retry — the direct cause of
    a live 'Request too large' 429 (input tokens exceeding the account's per-minute
    limit) hit in production. Java-only for now, matching every other `_fix_java_*`
    helper's existing per-language gating.
    """
    summarized: dict[str, str] = {}
    for path, content in files.items():
        if path in keep_full:
            summarized[path] = content
            continue
        base = path.rsplit("/", 1)[-1]
        if not path.endswith(".java") or base.upper().startswith("README") or base == "pom.xml":
            continue
        pieces = []
        cursor = 0
        for match in _JAVA_TOP_LEVEL_TYPE_RE.finditer(content):
            if match.start() < cursor:
                continue  # inside a type body already consumed above — don't re-enter it
            open_idx = content.find("{", match.end())
            if open_idx == -1:
                continue  # no body found (forward decl / malformed) — leave as-is
            close_idx = _find_matching_close_brace(content, open_idx)
            if close_idx == -1:
                continue  # unbalanced — leave as-is
            pieces.append(content[cursor:open_idx + 1])
            pieces.append(_strip_java_member_bodies(content[open_idx + 1:close_idx]))
            pieces.append("}")
            cursor = close_idx + 1
        pieces.append(content[cursor:])
        summarized[path] = "".join(pieces)
    return summarized


def _extract_secondary_type_to_own_file(
    content: str, simple_name: str, own_package: str
) -> tuple[str, str, str] | None:
    """Split a secondary top-level type out of a file that already has its own public
    type, into a new file named after it — the only way to legally make it `public`
    (javac requires exactly one public top-level type per file, matching the filename).

    Returns `(new_path, new_file_content, remaining_original_content)`, or `None` if the
    declaration (plus any directly-preceding annotations, e.g. `@Embeddable`) can't be
    unambiguously located and brace-matched.
    """
    pattern = re.compile(
        r"^((?:@[\w.]+(?:\([^)]*\))?[ \t]*\n)*)"
        r"((?:(?:public|final|abstract)\s+)*)"
        r"(class|interface|enum|record)(\s+" + re.escape(simple_name) + r"\b[^{]*)\{",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        return None
    open_brace_idx = match.end() - 1
    close_idx = _find_matching_close_brace(content, open_brace_idx)
    if close_idx == -1:
        return None

    decl_start, decl_end = match.start(), close_idx + 1
    annotations, _modifiers, kind, rest = match.groups()
    body_start = match.end()
    body = content[body_start:close_idx]
    extracted = f"{annotations}public {kind}{rest}{{{body}}}\n"

    # Bring over every import from the original file — safe over-inclusion, since an
    # unused import is a javac warning, never an error, and we have no cheap way to know
    # exactly which ones the extracted type actually needs.
    imports = re.findall(r"^import\s+(?:static\s+)?[\w.]+(?:\.\*)?\s*;\s*$", content, re.MULTILINE)
    new_content = f"package {own_package};\n\n"
    if imports:
        new_content += "\n".join(imports) + "\n\n"
    new_content += extracted

    remaining = content[:decl_start].rstrip() + "\n" + content[decl_end:].lstrip("\n")
    package_dir = own_package.replace(".", "/")
    new_path = f"src/main/java/{package_dir}/{simple_name}.java" if package_dir else f"src/main/java/{simple_name}.java"
    return new_path, new_content, remaining


def _insert_imports(content: str, imports: list[str]) -> str:
    """Insert additional Java import statements right after the file's `package` line.

    Function-delta injection only ever splices `function_body` between an existing
    method's braces — it has no way to touch the file's import section. When a delta's
    implementation legitimately needs a class from another package (or a JDK type) that
    the stub file doesn't already import, this is the only place that can add it. Each
    entry is tolerated in either form (`"java.time.LocalDate"` or
    `"import java.time.LocalDate;"`, including `static`); entries already present in
    `content` are skipped so retries don't pile up duplicates.
    """
    if not imports:
        return content
    existing = set(re.findall(r"^(import\s+(?:static\s+)?[\w.]+)\s*;", content, re.MULTILINE))
    new_lines = []
    for imp in imports:
        stmt = imp.strip().rstrip(";").strip()
        if not stmt.startswith("import"):
            stmt = f"import {stmt}"
        if stmt not in existing:
            new_lines.append(f"{stmt};")
            existing.add(stmt)
    if not new_lines:
        return content
    pkg_match = re.search(r"^\s*package\s+[\w.]+\s*;\s*\n", content, re.MULTILINE)
    insertion_point = pkg_match.end() if pkg_match else 0
    return content[:insertion_point] + "\n".join(new_lines) + "\n" + content[insertion_point:]


_JAVA_CLASS_OPEN_RE = re.compile(r"\bclass\s+\w+(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?\s*\{")


def _insert_fields(content: str, fields: list[str]) -> str:
    """Insert additional field declarations right after the class's opening brace.

    Same structural gap as `_insert_imports` but for fields: `function_body` only
    replaces a method body, so a delta that needs a repository/service the stub class
    never declared (a genuinely missing dependency, not just an invented one) has no way
    to add it — until now. Mirrors this codebase's existing `@Autowired` field-injection
    convention (see any already-fully-implemented method in the same skeleton). Entries
    already present in `content` (by exact statement match) are skipped.
    """
    if not fields:
        return content
    class_match = _JAVA_CLASS_OPEN_RE.search(content)
    if not class_match:
        return content
    new_lines = []
    for field in fields:
        stmt = field.strip().rstrip(";").strip()
        stmt = re.sub(r"^@Autowired\s*", "", stmt).strip()  # we add exactly one ourselves
        if stmt and stmt not in content:
            new_lines.append(stmt)
    if not new_lines:
        return content
        
    # Since we hardcode @Autowired for injected fields, we must ensure it's imported
    content = _insert_imports(content, ["org.springframework.beans.factory.annotation.Autowired"])
    class_match = _JAVA_CLASS_OPEN_RE.search(content)
    
    insertion_point = class_match.end()
    insertion_text = "\n\n" + "\n".join(f"    @Autowired\n    {stmt};" for stmt in new_lines) + "\n"
    return content[:insertion_point] + insertion_text + content[insertion_point:]


_CONSTRUCTOR_MISMATCH_RE = re.compile(
    r"constructor\s+(\w+)\s+in\s+(class|record)\s+([\w.]+)\s+cannot be applied to given types;\s*\n"
    r"\s*required:\s*(.*?)\s*\n"
    r"\s*found:\s*(.*?)\s*\n"
)
_JAVA_INSTANCE_FIELD_RE = re.compile(
    r"^\s*private\s+(?!static\b)[\w<>\[\],\s.]+?\s+(\w+)\s*(?:=.*)?;\s*$", re.MULTILINE
)
# Same field line, but also capturing the type — needed to write an explicit constructor
# (rather than just an annotation) for the "excludes the @Id field" case below.
_JAVA_TYPED_FIELD_RE = re.compile(
    r"^\s*private\s+(?!static\b)(?:final\s+)?([\w<>\[\],.]+?)\s+(\w+)\s*(?:=.*)?;\s*$", re.MULTILINE
)
# A field preceded by `@Id` (with optional other annotations, e.g. `@GeneratedValue`, in
# between) is the JPA-conventional auto-generated primary key — a structural/annotation
# fact, not a guess about business meaning.
_JAVA_ID_FIELD_RE = re.compile(
    r"@Id\b(?:\s*\n\s*@[\w.]+(?:\([^)]*\))?)*\s*\n\s*private\s+(?!static\b)(?:final\s+)?[\w<>\[\],.]+?\s+(\w+)\s*;"
)


def _fix_java_constructor_mismatch(files: dict[str, str], error_output: str) -> dict[str, str]:
    """Deterministically resolve the common, unambiguous constructor-arity mismatch:
    javac reporting a class has NO matching-arity constructor at all (not a type/order
    problem — a genuinely missing one).

    Deliberately narrow — every branch here is a Java/JPA/Lombok *convention* fix, never
    a guess about what the class *means*:

    1. Field count exactly matches the missing constructor's arg count → add the same
       Lombok annotation this codebase's own skeletons already use everywhere else
       (`@AllArgsConstructor` for a missing all-args constructor, `@NoArgsConstructor`
       for a missing no-arg one).
    2. All-args case only: field count is exactly one more than the arg count, and
       exactly one field is JPA-annotated `@Id` (the conventional auto-generated primary
       key, almost always omitted from convenience constructors) → generate an explicit
       constructor over every OTHER field, in declared order — still purely mechanical,
       identifying the excluded field via an annotation fact, not by inventing meaning.

    Never fires on records (a record's constructor mismatch means the CALLER has the
    wrong shape, not that an annotation is missing) or when a matching-arity constructor/
    the relevant annotation already exists (that's a real semantic bug, left for the LLM
    retry to resolve).
    """
    class_to_path: dict[str, str] = {}
    for path in files:
        m = re.search(r"src/main/java/(.+)\.java$", path)
        if m:
            class_to_path[m.group(1).replace("/", ".")] = path

    fixed = dict(files)
    for match in _CONSTRUCTOR_MISMATCH_RE.finditer(error_output):
        _simple_name, kind, fqcn, required, found = match.groups()
        if kind == "record":
            continue  # caller has the wrong shape, not a missing annotation

        required_empty = required.strip().lower() == "no arguments"
        found_empty = found.strip().lower() == "no arguments"
        if required_empty == found_empty:
            continue  # both empty (not this error) or both non-empty (ambiguous type/order)

        if required_empty:
            arg_count = len([a for a in found.split(",") if a.strip()])
            annotation = "AllArgsConstructor"
        else:
            arg_count = len([a for a in required.split(",") if a.strip()])
            annotation = "NoArgsConstructor"

        path = class_to_path.get(fqcn)
        if not path:
            continue  # can't safely locate the class
        content = fixed[path]

        if f"@{annotation}" in content:
            continue  # already has it — the mismatch must be something else

        typed_fields = _JAVA_TYPED_FIELD_RE.findall(content)  # [(type, name), ...] in order
        field_count = len(typed_fields)

        if field_count == arg_count:
            class_match = _JAVA_CLASS_OPEN_RE.search(content)
            if not class_match:
                continue
            line_start = content.rfind("\n", 0, class_match.start()) + 1
            content = content[:line_start] + f"@{annotation}\n" + content[line_start:]
            content = _insert_imports(content, [f"lombok.{annotation}"])
            if annotation == "AllArgsConstructor":
                # Java only auto-provides an implicit no-arg constructor when a class
                # declares NO other constructors — adding @AllArgsConstructor alone can
                # silently remove it out from under any OTHER caller that relied on
                # `new X()`. Preserve it explicitly unless already present.
                content = _preserve_noargs_constructor(content)
            fixed[path] = content
            log.info(f"ScaffoldGenerator: deterministically added @{annotation} to {fqcn} ({path})")
            continue

        # Common JPA pattern: convenience constructor omits the auto-generated @Id field.
        if annotation == "AllArgsConstructor" and field_count == arg_count + 1:
            id_fields = _JAVA_ID_FIELD_RE.findall(content)
            if len(id_fields) != 1:
                continue  # no @Id, or a composite key — ambiguous, leave for the LLM
            id_name = id_fields[0]
            non_id_fields = [(t, n) for t, n in typed_fields if n != id_name]
            if len(non_id_fields) != arg_count:
                continue  # still doesn't line up — don't guess further
            simple_name = fqcn.rsplit(".", 1)[-1]
            params = ", ".join(f"{t} {n}" for t, n in non_id_fields)
            assigns = "\n".join(f"        this.{n} = {n};" for _, n in non_id_fields)
            ctor = f"\n    public {simple_name}({params}) {{\n{assigns}\n    }}\n"
            class_match = _JAVA_CLASS_OPEN_RE.search(content)
            if not class_match:
                continue
            insertion_point = class_match.end()
            content = content[:insertion_point] + ctor + content[insertion_point:]
            # Same implicit-no-arg-constructor loss as above — this branch adds an
            # explicit constructor too.
            content = _preserve_noargs_constructor(content)
            fixed[path] = content
            log.info(
                f"ScaffoldGenerator: deterministically added an explicit constructor "
                f"(excluding @Id field {id_name!r}) to {fqcn} ({path})"
            )

    return fixed


def _preserve_noargs_constructor(content: str) -> str:
    """Java only auto-provides an implicit no-arg constructor when a class declares NO
    other constructors. `_fix_java_constructor_mismatch` adds an explicit one to satisfy
    one caller — this keeps any OTHER caller that relied on `new X()` still working, by
    adding `@NoArgsConstructor` explicitly unless the class already has it.
    """
    if "@NoArgsConstructor" in content:
        return content
    class_match = _JAVA_CLASS_OPEN_RE.search(content)
    if not class_match:
        return content
    line_start = content.rfind("\n", 0, class_match.start()) + 1
    content = content[:line_start] + "@NoArgsConstructor\n" + content[line_start:]
    return _insert_imports(content, ["lombok.NoArgsConstructor"])


_REPO_METHOD_MISSING_RE = re.compile(
    r"cannot find symbol\s*\n"
    r"\s*symbol:\s*method\s+(\w+)\(([^)]*)\)\s*\n"
    r"\s*location:\s*variable\s+\w+\s+of type\s+([\w.]+)"
)
_JPA_REPO_EXTENDS_RE = re.compile(
    r"\bextends\s+(?:JpaRepository|CrudRepository|PagingAndSortingRepository)\s*<\s*(\w+)\s*,"
)
_JAVA_INTERFACE_OPEN_RE = re.compile(r"\binterface\s+\w+\s+extends\s+[\w<>,\s]+\{")


def _fix_java_repository_method(files: dict[str, str], error_output: str) -> dict[str, str]:
    """Deterministically declare a missing Spring Data JPA derived-query method on a
    repository interface — but ONLY the two prefixes with zero return-type ambiguity in
    Spring Data's own naming convention: `existsBy...` (always `boolean`) and
    `countBy...` (always `long`). `findBy...`/`getBy...` are deliberately excluded —
    those are genuinely ambiguous (single entity vs. `Optional` vs. `List`) and need the
    LLM to decide.

    Spring Data only implements a derived query method that's explicitly declared in the
    repository interface — matching the naming convention isn't enough by itself, which
    is exactly why this compiles-time error happens. This mirrors that same convention
    mechanically: split the method name's `By...And...Or...` suffix into field-name
    segments and verify every one matches an actual field the entity declares (a
    structural fact, not a guess) before declaring the method. If anything doesn't line
    up — an unrecognized segment, an arg-count mismatch, an unrecognized repository base
    interface — this is left untouched for the LLM rather than guessing further.
    """
    class_to_path: dict[str, str] = {}
    simple_to_fqcn: dict[str, str | None] = {}
    for path in files:
        m = re.search(r"src/main/java/(.+)\.java$", path)
        if m:
            fqcn = m.group(1).replace("/", ".")
            class_to_path[fqcn] = path
            simple_name = fqcn.rsplit(".", 1)[-1]
            simple_to_fqcn[simple_name] = None if simple_name in simple_to_fqcn else fqcn

    fixed = dict(files)
    for match in _REPO_METHOD_MISSING_RE.finditer(error_output):
        method_name, arg_types_str, repo_fqcn = match.groups()

        if method_name.startswith("existsBy"):
            prefix, return_type = "existsBy", "boolean"
        elif method_name.startswith("countBy"):
            prefix, return_type = "countBy", "long"
        else:
            continue  # findBy/getBy/etc — genuinely ambiguous, leave for the LLM

        repo_path = class_to_path.get(repo_fqcn)
        if not repo_path:
            continue  # can't safely locate the repository
        repo_content = fixed[repo_path]

        if re.search(rf"\b{re.escape(method_name)}\s*\(", repo_content):
            continue  # already declared — the mismatch must be something else

        entity_match = _JPA_REPO_EXTENDS_RE.search(repo_content)
        if not entity_match:
            continue  # not a recognizable Spring Data repository — don't guess
        entity_fqcn = simple_to_fqcn.get(entity_match.group(1))
        entity_path = class_to_path.get(entity_fqcn) if entity_fqcn else None
        if not entity_path:
            continue  # entity ambiguous or not found
        entity_content = fixed[entity_path]
        entity_fields = set(_JAVA_INSTANCE_FIELD_RE.findall(entity_content))

        suffix = method_name[len(prefix):]
        segments = [s for s in re.split(r"And(?=[A-Z])|Or(?=[A-Z])", suffix) if s]
        field_names = []
        for seg in segments:
            candidate = seg[0].lower() + seg[1:]
            if candidate not in entity_fields:
                field_names = None
                break
            field_names.append(candidate)
        if not field_names:
            continue  # a segment doesn't match any real field — don't guess further

        arg_types = [t.strip() for t in arg_types_str.split(",") if t.strip()]
        if len(arg_types) != len(field_names):
            continue  # argument count doesn't line up with the parsed field segments

        params = ", ".join(f"{t} {n}" for t, n in zip(arg_types, field_names))
        interface_match = _JAVA_INTERFACE_OPEN_RE.search(repo_content)
        if not interface_match:
            continue
        insertion_point = interface_match.end()
        declaration = f"\n    {return_type} {method_name}({params});\n"
        repo_content = repo_content[:insertion_point] + declaration + repo_content[insertion_point:]
        fixed[repo_path] = repo_content
        log.info(
            f"ScaffoldGenerator: deterministically declared missing repository method "
            f"{method_name} on {repo_fqcn} ({repo_path})"
        )

    return fixed


def _fix_java_missing_entity_field(files: dict[str, str], error_output: str) -> dict[str, str]:
    """Deterministically add a missing plain field to a Lombok-annotated class when the
    error is a missing get/is/set accessor on a class OTHER than the one being edited.
    This exists because the delta phase (`FunctionDeltaOutput`) can only edit the stub's
    own file — if generated logic needs a field on a sibling class, no amount of LLM
    retrying inside that phase can fix it; only this deterministic pass or the
    gold-master-assembly LLM patch (which CAN edit arbitrary files) can.

    Field type is a pragmatic default, not a certainty: `is` prefix -> `boolean` (always
    correct by Java/Lombok convention); `get`/`set` prefix -> `Integer = 0` (right for the
    common case of counters/scores/etc., wrong for non-numeric fields). Safe either way:
    compile validation re-checks the result before it's ever accepted, and a wrong guess
    just leaves the pipeline exactly as stuck as before this fix existed — never worse.
    """
    class_to_path: dict[str, str] = {}
    for path in files:
        m = re.search(r"src/main/java/(.+)\.java$", path)
        if m:
            class_to_path[m.group(1).replace("/", ".")] = path

    fixed = dict(files)
    added: set[tuple[str, str]] = set()
    for method_name, _args, owner_fqcn in _REPO_METHOD_MISSING_RE.findall(error_output):
        accessor_match = re.match(r"^(get|is|set)([A-Z]\w*)$", method_name)
        if not accessor_match:
            continue
        prefix, name = accessor_match.groups()
        field_name = name[0].lower() + name[1:]

        owner_path = class_to_path.get(owner_fqcn)
        if not owner_path or owner_path not in fixed:
            continue  # can't safely locate the owning class
        if (owner_path, field_name.lower()) in added:
            continue

        owner_content = fixed[owner_path]
        if not re.search(r"@(Getter|Setter|Data)\b", owner_content):
            continue  # not Lombok-managed — don't guess at hand-written accessors

        existing_fields = {f.lower() for f in _JAVA_INSTANCE_FIELD_RE.findall(owner_content)}
        if field_name.lower() in existing_fields:
            continue  # exists under a different case — real bug, leave to LLM

        class_match = _JAVA_CLASS_OPEN_RE.search(owner_content)
        if not class_match:
            continue

        field_type, default = ("boolean", "false") if prefix == "is" else ("Integer", "0")
        declaration = f"\n\n    private {field_type} {field_name} = {default};\n"
        owner_content = owner_content[:class_match.end()] + declaration + owner_content[class_match.end():]
        fixed[owner_path] = owner_content
        added.add((owner_path, field_name.lower()))
        log.info(
            f"ScaffoldGenerator: deterministically added missing field '{field_name}' "
            f"({field_type}) to {owner_fqcn} ({owner_path}) — resolves missing "
            f"{method_name}() accessor"
        )

    return fixed


def _try_deterministic_fix(files: dict[str, str], error_output: str, language: str) -> tuple[dict[str, str], bool]:
    """Attempt structural, Java-convention-only fixes before falling back to an LLM
    patch — cheaper and more reliable than a round-trip for well-understood mismatches.
    Never touches business logic; see `_fix_java_constructor_mismatch`'s docstring for
    the exact, narrow scope this covers.
    """
    if language != "java":
        return files, False
    fixed = _fix_java_constructor_mismatch(files, error_output)
    fixed = _fix_java_repository_method(fixed, error_output)
    fixed = _fix_java_missing_entity_field(fixed, error_output)
    return fixed, fixed != files


def _replace_function_body(content: str, fn_name: str, new_body: str, language: str) -> str:
    """Fallback injection: find fn_name in content and replace its throw/raise with new_body.

    Used when the exact stub marker wasn't found (LLM used a slightly different message).
    For brace-delimited languages (Node/Java): finds function by name, counts braces to
    locate the body, replaces the single throw statement inside.
    For Python: finds the def line and replaces the raise statement in the body.
    """
    if language == "python":
        lines = content.split("\n")
        fn_def_idx = None
        fn_indent = 0
        for i, line in enumerate(lines):
            m = re.match(rf'^(\s*)def\s+{re.escape(fn_name)}\s*\(', line)
            if m:
                fn_def_idx = i
                fn_indent = len(m.group(1))
                break
        if fn_def_idx is None:
            log.warning(f"_replace_function_body: def {fn_name}( not found in Python file")
            return content
        # Walk forward to find the raise/pass in the body
        for i in range(fn_def_idx + 1, len(lines)):
            stripped = lines[i].lstrip()
            if not stripped:
                continue
            line_indent = len(lines[i]) - len(stripped)
            if line_indent <= fn_indent:
                break  # left the function
            if stripped.startswith(("raise ", "pass")):
                lines[i] = " " * line_indent + new_body.strip()
                return "\n".join(lines)
        log.warning(f"_replace_function_body: no raise/pass found in def {fn_name}()")
        return content
    else:
        # Node / Java: brace-counted body replacement
        fn_match = re.search(rf'\b{re.escape(fn_name)}\s*\(', content)
        if not fn_match:
            log.warning(f"_replace_function_body: {fn_name}( not found")
            return content
        brace_start = content.find("{", fn_match.end())
        if brace_start == -1:
            log.warning(f"_replace_function_body: no opening brace after {fn_name}(")
            return content
        depth = 0
        brace_end = -1
        for i in range(brace_start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break
        if brace_end == -1:
            log.warning(f"_replace_function_body: unmatched braces for {fn_name}")
            return content
        # Preserve body indentation from the original throw line
        original_body = content[brace_start + 1:brace_end]
        indent_match = re.search(r'\n(\s+)', original_body)
        indent = indent_match.group(1) if indent_match else "  "
        return (
            content[:brace_start + 1]
            + "\n" + indent + new_body.strip() + "\n"
            + content[brace_end:]
        )

# Stub throw statement per language — must match what the skeleton prompt generates
_STUB_THROW = {
    "node": "throw new Error('not implemented: {tag}');",
    "java": 'throw new UnsupportedOperationException("not implemented: {tag}");',
    "python": 'raise NotImplementedError("not implemented: {tag}")',
}


class ScaffoldGenerator:
    """Three-phase CoT generator — skeleton + delta architecture.

    Phase 1:  design_challenge         → 3 tiers × N scenarios design document
    Phase 2a: implement_skeleton_{lang} × 3 → full codebase per tier; all N target
              functions are explicit stubs (`throw new Error('not implemented: ...')`).
              Non-target functions are fully implemented as pattern examples.
    Phase 2b: implement_function_{lang} × 3N → implements exactly one stubbed function
              per call and generates its hidden test file.

    Assembly:
      gold master = skeleton with ALL N function bodies injected back (for blueprint + tests)
      student scaffold = skeleton unchanged (stubs as-is) + scenario-specific README

    Phase 3: generate_blueprint × 3N → blueprints stored in Postgres + Redis
    """

    def generate_design_only(
        self,
        problem_description: str,
        languages: list[str] | None = None,
        tiers: list[str] | None = None,
        scenarios_per_tier: int = 3,
        debug_scenarios_per_tier: int = 1,
        non_deterministic_scenarios_per_tier: int = 0,
        feedback: str | None = None,
    ) -> dict:
        """Run Phase 1 only — returns the DesignOutput as a dict for admin review."""
        active_languages = languages or ["node"]
        active_tiers = tiers or list(_TIERS)
        llm_client.reset_session_cost()
        clean_description = sanitizer.sanitize_description(problem_description)

        design_system = llm_client.load_prompt("design_challenge")
        feedback_block = f"\n\n<admin_feedback>\n{feedback}\n</admin_feedback>" if feedback else ""
        design_user_msg = (
            f"<languages>{','.join(active_languages)}</languages>\n"
            f"<tiers>{','.join(active_tiers)}</tiers>\n"
            f"<scenarios_per_tier>{scenarios_per_tier}</scenarios_per_tier>\n"
            f"<debug_scenarios_per_tier>{debug_scenarios_per_tier}</debug_scenarios_per_tier>\n"
            f"<non_deterministic_scenarios_per_tier>{non_deterministic_scenarios_per_tier}</non_deterministic_scenarios_per_tier>\n"
            f"<allowed_topics>{','.join(_TOPICS)}</allowed_topics>\n"
            f"<problem>\n{clean_description}\n</problem>"
            f"{feedback_block}"
        )
        raw_design = llm_client.complete_json(design_system, design_user_msg, label="design")
        design: DesignOutput = validate_with_correction(
            raw_design, DesignOutput, llm_client.complete_json,
            design_system, design_user_msg, label="design-validate",
        )
        log.info(f"generate_design_only: complete — challenge={design.challenge.get('name')}")
        return design.model_dump()

    def generate(
        self,
        problem_description: str,
        languages: list[str] | None = None,
        use_local_few_shots: bool = False,
        tiers: list[str] | None = None,
        scenarios_per_tier: int = 3,
        debug_scenarios_per_tier: int = 1,
        non_deterministic_scenarios_per_tier: int = 0,
        design_json: str | dict | None = None,
    ) -> dict:
        active_languages: list[str] = languages or ["node"]
        active_tiers: list[str] = tiers or list(_TIERS)

        for lang in active_languages:
            if lang not in _SUPPORTED_LANGUAGES:
                raise ValueError(f"Unsupported language {lang!r}. Choose from: {_SUPPORTED_LANGUAGES}")

        llm_client.reset_session_cost()
        clean_description = sanitizer.sanitize_description(problem_description)

        few_shot_context = ""
        if use_local_few_shots:
            few_shot_context = load_few_shot_repos() + "\n"

        # ── Phase 1 — Architecture Design (skip if design_json supplied, or a cached
        # design from an earlier attempt at this exact request already exists — Phase 1's
        # output is a fixed fact once produced, re-running it on every retry just
        # re-spends tokens for an identical result) ──────────────────────────────────
        design_cache_key: str | None = None
        if design_json is not None:
            import json as _json
            raw = design_json if isinstance(design_json, str) else _json.dumps(design_json)
            design: DesignOutput = DesignOutput.model_validate_json(raw)
            log.info(f"ScaffoldGenerator: Phase 1 skipped — using pre-approved design")
        else:
            design_cache_key = "codegen:design:" + hashlib.sha256(
                json.dumps(
                    {
                        "prompt": clean_description,
                        "languages": sorted(active_languages),
                        "tiers": sorted(active_tiers),
                        "scenarios_per_tier": scenarios_per_tier,
                        "debug_scenarios_per_tier": debug_scenarios_per_tier,
                        "non_deterministic_scenarios_per_tier": non_deterministic_scenarios_per_tier,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            cached_design = cache_client.get(design_cache_key)
            if cached_design:
                design: DesignOutput = DesignOutput.model_validate_json(cached_design)
                log.info("ScaffoldGenerator: Phase 1 cache hit — resuming without re-running design")
            else:
                design_system = llm_client.load_prompt("design_challenge")
                log.info(f"ScaffoldGenerator: Phase 1 (design, tiers={active_tiers}, scenarios_per_tier={scenarios_per_tier}, debug_scenarios_per_tier={debug_scenarios_per_tier}, non_deterministic_scenarios_per_tier={non_deterministic_scenarios_per_tier})")
                design_user_msg = (
                    f"<languages>{','.join(active_languages)}</languages>\n"
                    f"<tiers>{','.join(active_tiers)}</tiers>\n"
                    f"<scenarios_per_tier>{scenarios_per_tier}</scenarios_per_tier>\n"
                    f"<debug_scenarios_per_tier>{debug_scenarios_per_tier}</debug_scenarios_per_tier>\n"
                    f"<non_deterministic_scenarios_per_tier>{non_deterministic_scenarios_per_tier}</non_deterministic_scenarios_per_tier>\n"
                    f"<allowed_topics>{','.join(_TOPICS)}</allowed_topics>\n"
                    f"<problem>\n{clean_description}\n</problem>"
                )
                raw_design = llm_client.complete_json(design_system, design_user_msg, label="design")
                design: DesignOutput = validate_with_correction(
                    raw_design, DesignOutput, llm_client.complete_json,
                    design_system, design_user_msg, label="design-validate",
                )
                cache_client.set(design_cache_key, design.model_dump_json(), expire=60 * 60 * 24)

        # Verify the LLM produced the requested tiers with the right scenario count
        for tier in active_tiers:
            if tier not in design.difficulty_tiers:
                raise ValueError(
                    f"Design output missing tier '{tier}' — got: {list(design.difficulty_tiers.keys())}"
                )
            actual_count = len(design.difficulty_tiers[tier].get("scenarios", []))
            if actual_count != scenarios_per_tier:
                raise ValueError(
                    f"Tier '{tier}' has {actual_count} scenarios, expected {scenarios_per_tier}"
                )

        challenge_name = design.challenge.get("name", "challenge")
        # The LLM can independently produce the same challenge_name for genuinely
        # different designs (e.g. same domain prompt, different scenarios_per_tier) —
        # challenge_name alone is NOT a safe cache-scoping key. Fingerprint the actual
        # resolved design content (regardless of whether it came from a fresh Phase 1
        # call, the design cache, or an admin-supplied design_json) so a skeleton/delta
        # cached under one design can never be reused for a structurally different one.
        design_fingerprint = hashlib.sha256(design.model_dump_json().encode()).hexdigest()[:16]
        log.info(f"ScaffoldGenerator: Phase 1 complete — challenge={challenge_name}")

        # ── Phase 2 — Per language: skeleton + deltas + upload ───────────────────
        all_manifests: dict[str, dict] = {}
        failed_scaffolds: list[str] = []
        failed_blueprints: list[str] = []
        generated_blueprints: dict[str, dict] = {}

        for language in active_languages:
            log.info(f"ScaffoldGenerator: Phase 2 start — language={language}")
            skipped_tiers: set[str] = set()

            # Phase 2a — Skeleton per tier
            skeleton_system = llm_client.load_prompt(f"implement_skeleton_{language}")
            tier_skeletons: dict[str, SkeletonOutput] = {}

            for tier in active_tiers:
                checkpoint_key = f"codegen:checkpoint:{challenge_name}:{design_fingerprint}:{language}:{tier}"
                if cache_client.get(checkpoint_key) == "completed":
                    log.info(f"ScaffoldGenerator: checkpoint hit — skipping tier={tier} lang={language}")
                    skipped_tiers.add(tier)
                    continue

                # A previously-compiled skeleton is a fixed, already-verified fact — reuse
                # it and skip straight to Phase 2b instead of re-spending every Phase 2a
                # LLM call (including up to _MAX_SKELETON_COMPILE_RETRIES+1 of them) just
                # because a LATER stage (a delta, or gold-master) failed on a prior attempt.
                skeleton_cache_key = f"codegen:skeleton:{challenge_name}:{design_fingerprint}:{language}:{tier}"
                cached_skeleton = cache_client.get(skeleton_cache_key)
                if cached_skeleton:
                    skeleton: SkeletonOutput = SkeletonOutput.model_validate_json(cached_skeleton)
                    tier_skeletons[tier] = skeleton
                    log.info(
                        f"ScaffoldGenerator: skeleton cache hit — resuming lang={language}, "
                        f"tier={tier}, skipping Phase 2a"
                    )
                else:
                    tier_design = design.difficulty_tiers[tier]
                    scenarios_json = json.dumps(tier_design["scenarios"], indent=2)
                    user_context = (
                        f"{few_shot_context}"
                        f"<problem>\n{clean_description}\n</problem>\n\n"
                        f"<design>\n{json.dumps(design.model_dump(), indent=2)}\n</design>\n\n"
                        f"<tier>{tier.upper()}</tier>\n"
                        f"<scenarios>\n{scenarios_json}\n</scenarios>"
                    )
                    scenario_tags = [s["scenario_tag"] for s in tier_design["scenarios"]]
                    log.info(f"ScaffoldGenerator: Phase 2a skeleton — lang={language}, tier={tier}, scenarios={scenario_tags}")
                    raw_skeleton = llm_client.complete_json_cached(
                        skeleton_system,
                        user_context,
                        label=f"skeleton-{language}-{tier}",
                        max_tokens_override=settings.openai_max_tokens_impl,
                    )
                    skeleton: SkeletonOutput = validate_with_correction(
                        raw_skeleton,
                        SkeletonOutput,
                        lambda sys, usr, l=language, t=tier: llm_client.complete_json_cached(
                            sys, usr,
                            label=f"skeleton-{l}-{t}-retry",
                            max_tokens_override=settings.openai_max_tokens_impl,
                        ),
                        skeleton_system,
                        user_context,
                        label=f"skeleton-{language}-{tier}-validate",
                    )
                    if language == "java":
                        skeleton.files["pom.xml"] = _JAVA_POM_TEMPLATE
                        skeleton.files["src/main/java/com/challenge/ChallengeApplication.java"] = _JAVA_APP_TEMPLATE
                        skeleton.files = _fix_java_source_paths(skeleton.files)
                        skeleton.files = _fix_java_imports(skeleton.files)
                        log.info("ScaffoldGenerator: injected pinned pom.xml + ChallengeApplication.java (java)")
                    tier_skeletons[tier] = skeleton
                    log.info(f"ScaffoldGenerator: Phase 2a done — lang={language}, tier={tier}, files={list(skeleton.files.keys())}")

                    # Validate the skeleton compiles before Phase 2b (catches missing DTO/model files).
                    # Retries patch incrementally rather than regenerating the whole skeleton: a full
                    # regeneration is a fresh completion guided only by the previous error's hint, and
                    # can fix the flagged issue while silently dropping something that was already
                    # correct (e.g. forgetting a DTO it had before) — a structural risk that gets worse,
                    # not better, with more attempts, since the model must reproduce the entire
                    # multi-file codebase from memory every single time. Showing it the current files
                    # and asking for only the new/corrected file(s) keeps everything already-working
                    # untouched and lets fixes accumulate across retries instead of being re-risked.
                    _MAX_SKELETON_COMPILE_RETRIES = 4
                    skeleton_compile_attempt = 0
                    while True:
                        try:
                            # run_tests=True: also EXECUTES the skeleton's own required
                            # starter test (implement_skeleton_java.mdx's "at least one
                            # fully implemented test file"), not just compiles it. Catches
                            # a real recurring bug class here, with the full skeleton-retry
                            # budget, instead of only at the much more constrained
                            # gold-master retry stage: the skeleton's own Flyway seed data
                            # and its own starter test are written in the same completion
                            # with no cross-check between them (e.g. seed data already
                            # containing a "duplicate" row the starter test then asserts
                            # doesn't get rejected as a duplicate).
                            compile_validator.validate_compilation(skeleton.files, language, run_tests=True)
                            log.info(f"ScaffoldGenerator: skeleton compiled OK — lang={language}, tier={tier}")
                            break
                        except CompileValidationError as e:
                            if _is_only_stub_related_test_failure(str(e)):
                                # The starter test happened to exercise a scenario's own
                                # target-stub method — expected to fail at this stage (the
                                # stub hasn't been implemented yet), not a real bug. Treat
                                # exactly like a successful validation.
                                log.info(
                                    f"ScaffoldGenerator: skeleton test failure is an expected "
                                    f"not-yet-implemented stub — treating as OK — lang={language}, tier={tier}"
                                )
                                break

                            # Try a Java-convention-only deterministic fix first — free (no
                            # LLM call, doesn't consume a retry attempt) and more reliable
                            # than a round-trip for well-understood structural mismatches.
                            candidate_files, changed = _try_deterministic_fix(skeleton.files, str(e), language)
                            if changed:
                                try:
                                    compile_validator.validate_compilation(candidate_files, language, run_tests=True)
                                    skeleton.files = candidate_files
                                    log.info(
                                        f"ScaffoldGenerator: skeleton compile error resolved "
                                        f"deterministically (no LLM call needed) — lang={language}, tier={tier}"
                                    )
                                    continue
                                except CompileValidationError:
                                    skeleton.files = candidate_files  # keep partial fix either way

                            if skeleton_compile_attempt >= _MAX_SKELETON_COMPILE_RETRIES:
                                if _is_test_execution_failure(str(e)):
                                    # Code compiles — only the skeleton's own test still
                                    # doesn't fully pass. Never make the pipeline strictly
                                    # worse than before Phase 2a ran tests at all: fall
                                    # back to the pre-existing compile-only acceptance
                                    # instead of hard-failing the whole generation over a
                                    # test-only issue that gold master would previously
                                    # have silently inherited anyway.
                                    try:
                                        compile_validator.validate_compilation(skeleton.files, language, run_tests=False)
                                        log.warning(
                                            f"ScaffoldGenerator: skeleton's own starter test still fails "
                                            f"after {_MAX_SKELETON_COMPILE_RETRIES + 1} attempts, but the "
                                            f"code compiles — proceeding anyway rather than failing the "
                                            f"whole generation over a test-only issue. lang={language}, "
                                            f"tier={tier}"
                                        )
                                        break
                                    except CompileValidationError:
                                        pass  # doesn't even compile-only anymore — fall through to raise
                                log.error(
                                    f"ScaffoldGenerator: skeleton compilation failed after "
                                    f"{_MAX_SKELETON_COMPILE_RETRIES + 1} attempts for lang={language}, tier={tier}"
                                )
                                raise
                            skeleton_compile_attempt += 1
                            hint = _classify_compile_error(str(e))
                            log.warning(f"ScaffoldGenerator: skeleton compile failed — {hint}. Patching skeleton.")
                            # Signature-only for Java: the full file dump here (every retry)
                            # is what caused a live 'Request too large' 429 on a big skeleton —
                            # method bodies aren't needed to fix a compile error at the
                            # class/import/signature level, just the exact shapes involved.
                            context_files = (
                                _java_signature_summary(skeleton.files) if language == "java" else skeleton.files
                            )
                            patch_context = (
                                f"{user_context}\n\n"
                                f"<current_skeleton_files>\n{json.dumps(context_files, indent=2)}\n</current_skeleton_files>\n\n"
                                f"The skeleton above failed to compile:\n{e}\n\n"
                                f"How to fix: {hint}\n\n"
                                f"Do NOT regenerate the whole skeleton. Return ONLY the new file(s) to add "
                                f"or the corrected content of the specific existing file(s) that need to "
                                f"change to fix this error — every other file in <current_skeleton_files> "
                                f"stays exactly as shown and must be omitted from your response. If a file "
                                f"needs to be deleted entirely (e.g. a genuine duplicate class), list its "
                                f"path in `remove_files` instead of rewriting it. "
                                f'Output JSON of the form: {{"files": {{"path/to/File.java": "..."}}, '
                                f'"remove_files": ["path/to/DeleteMe.java"]}}.'
                            )
                            raw_patch = llm_client.complete_json_cached(
                                skeleton_system,
                                patch_context,
                                label=f"skeleton-{language}-{tier}-compile-retry",
                                max_tokens_override=settings.openai_max_tokens_impl,
                            )
                            patch: SkeletonPatchOutput = validate_with_correction(
                                raw_patch,
                                SkeletonPatchOutput,
                                lambda sys, usr, l=language, t=tier: llm_client.complete_json_cached(
                                    sys, usr,
                                    label=f"skeleton-{l}-{t}-compile-retry-schema",
                                    max_tokens_override=settings.openai_max_tokens_impl,
                                ),
                                skeleton_system,
                                patch_context,
                                label=f"skeleton-{language}-{tier}-compile-retry-validate",
                            )
                            for removed_path in patch.remove_files:
                                skeleton.files.pop(removed_path, None)
                            skeleton.files.update(patch.files)
                            if language == "java":
                                skeleton.files = _fix_java_source_paths(skeleton.files)
                                skeleton.files = _fix_java_imports(skeleton.files)
                            tier_skeletons[tier] = skeleton
                            log.info(
                                f"ScaffoldGenerator: skeleton patched — lang={language}, tier={tier}, "
                                f"patched_files={list(patch.files.keys())}, removed_files={patch.remove_files}, "
                                f"total_files={list(skeleton.files.keys())}"
                            )

                    cache_client.set(skeleton_cache_key, skeleton.model_dump_json(), expire=60 * 60 * 24)
                    log.info(f"ScaffoldGenerator: skeleton cached — lang={language}, tier={tier}")

            # Phase 2b — Function deltas per scenario
            tier_deltas: dict[str, dict[str, FunctionDeltaOutput]] = {}
            tier_qa_reports: dict[str, dict[str, dict]] = {}

            for tier in active_tiers:
                if tier in skipped_tiers:
                    continue
                skeleton = tier_skeletons[tier]
                tier_design = design.difficulty_tiers[tier]
                tier_deltas[tier] = {}
                tier_qa_reports[tier] = {}

                for scenario in tier_design["scenarios"]:
                    tag = scenario["scenario_tag"]

                    # A previously-compiled delta is a fixed, already-verified fact —
                    # reuse it instead of re-spending its LLM calls (including retries)
                    # just because a DIFFERENT scenario or the gold-master step failed
                    # on a prior attempt at this same request.
                    delta_cache_key = f"codegen:delta:{challenge_name}:{design_fingerprint}:{language}:{tier}:{tag}"
                    cached_delta = cache_client.get(delta_cache_key)
                    if cached_delta:
                        tier_deltas[tier][tag] = FunctionDeltaOutput.model_validate_json(cached_delta)
                        log.info(
                            f"ScaffoldGenerator: delta cache hit — resuming lang={language}, "
                            f"scenario={tag}, skipping Phase 2b"
                        )
                        continue

                    scenario_type = scenario.get("type", "implement")
                    check_mode = scenario.get("check_mode", "deterministic")
                    prompt_name = _select_delta_prompt_name(language, scenario_type, check_mode)
                    function_system = llm_client.load_prompt(prompt_name)
                    stub_loc = skeleton.stub_locations.get(tag)
                    stub_file_content = (
                        skeleton.files.get(stub_loc.file, "") if stub_loc else ""
                    )
                    # Signature-only for every OTHER file: the stub file itself is already
                    # sent in full above via <stub_file_content>, so keep_full excludes it
                    # from being duplicated. Cuts prompt size on every scenario/every retry —
                    # the direct cause of a live 'Request too large' 429 on a large skeleton.
                    full_skeleton_context = (
                        _java_signature_summary(skeleton.files, keep_full=frozenset({stub_loc.file} if stub_loc else set()))
                        if language == "java" else skeleton.files
                    )
                    user_context = (
                        f"<tier>{tier.upper()}</tier>\n"
                        f"<scenario_tag>{tag}</scenario_tag>\n"
                        f"<scenario_title>{scenario['title']}</scenario_title>\n"
                        f"<scenario_description>{scenario['description']}</scenario_description>\n"
                        f"<bug_description>{scenario.get('bug_description', '')}</bug_description>\n"
                        f"<strip_description>{scenario.get('strip_description', '')}</strip_description>\n"
                        f"<stub_file>{stub_loc.file if stub_loc else ''}</stub_file>\n"
                        f"<stub_file_content>\n{stub_file_content}\n</stub_file_content>\n"
                        f"<full_skeleton>\n{json.dumps(full_skeleton_context, indent=2)}\n</full_skeleton>\n"
                        f"<skeleton_classes>\n{_skeleton_classes_summary(skeleton.files)}\n</skeleton_classes>"
                    )
                    delta_system = function_system
                    delta_user_context = user_context
                    attempt = 0
                    max_attempts = 3
                    delta = None
                    
                    while attempt <= max_attempts:
                        raw_delta = llm_client.complete_json(
                            delta_system,
                            delta_user_context,
                            label=f"function-{language}-{tag}-att{attempt}",
                            max_tokens_override=settings.openai_max_tokens_test,
                        )
                        delta = validate_with_correction(
                            raw_delta,
                            FunctionDeltaOutput,
                            llm_client.complete_json,
                            delta_system,
                            delta_user_context,
                            label=f"function-{language}-{tag}-validate",
                        )
                        
                        # Validate compilation for this delta specifically
                        test_files = self._inject_all_deltas(skeleton.files, {tag: delta}, language, skeleton)
                        if language == "java":
                            test_files = _fix_java_source_paths(test_files)
                            test_files = _fix_java_imports(test_files)
                        safe_test_files = sanitizer.sanitize_generated_files(test_files)
                        try:
                            compile_validator.validate_compilation(safe_test_files, language)
                            break # Success!
                        except CompileValidationError as e:
                            # Try a Java-convention-only deterministic fix first — free
                            # (no LLM call, doesn't consume a retry attempt). The mismatch
                            # is almost always in a skeleton-owned file (e.g. a model
                            # class), not the stub file this delta just modified, so
                            # persist it onto skeleton.files for every later scenario and
                            # the gold-master assembly to benefit too.
                            candidate_files, changed = _try_deterministic_fix(test_files, str(e), language)
                            if changed:
                                stub_path = stub_loc.file if stub_loc else None
                                try:
                                    safe_candidate = sanitizer.sanitize_generated_files(candidate_files)
                                    compile_validator.validate_compilation(safe_candidate, language)
                                    for p, c in candidate_files.items():
                                        if p != stub_path and skeleton.files.get(p) != c:
                                            skeleton.files[p] = c
                                    log.info(
                                        f"ScaffoldGenerator: delta compile error resolved "
                                        f"deterministically (no LLM call needed) — scenario={tag}"
                                    )
                                    break
                                except CompileValidationError:
                                    pass  # didn't fully resolve it — fall through to the LLM patch

                            attempt += 1
                            if attempt > max_attempts:
                                log.error(f"ScaffoldGenerator: Delta compilation failed after {max_attempts} attempts for scenario={tag}")
                                raise e
                            log.warning(f"Delta compilation failed (attempt {attempt}): {e}. Sending compiler error to LLM for correction.")
                            targeted_hint = _classify_compile_error(str(e), delta_phase=True)
                            delta_user_context = (
                                f"{user_context}\n\n"
                                f"Your previous implementation caused a compilation error:\n{e}\n\n"
                                f"How to fix: {targeted_hint}\n\n"
                                f"Please return the corrected JSON with all issues resolved."
                            )

                    # Phase 4 — LLM-judge QA gate. Runs once this delta compiles, before
                    # gold-master merge/upload — cheapest point to catch a miscalibrated
                    # scenario. Self-heals the same way the compile-retry loop above does:
                    # feed the judge's findings back into a fresh delta call, capped, then
                    # hard-fail the job if it still doesn't pass.
                    qa_attempt = 0
                    while True:
                        qa_verdict = self._run_scenario_qa(language, tier, scenario, delta)
                        if qa_verdict.overall_pass:
                            break
                        qa_attempt += 1
                        if qa_attempt > _MAX_QA_RETRIES:
                            error_msg = (
                                f"ScaffoldGenerator: scenario QA failed after {_MAX_QA_RETRIES} "
                                f"retries — lang={language}, scenario={tag}: {qa_verdict.findings} "
                                f"(issues: {qa_verdict.test_issues})"
                            )
                            log.error(error_msg)
                            raise RuntimeError(error_msg)
                        log.warning(
                            f"ScaffoldGenerator: scenario QA failed (attempt {qa_attempt}) — "
                            f"lang={language}, scenario={tag}: {qa_verdict.findings}. Regenerating."
                        )
                        delta_user_context = (
                            f"{user_context}\n\n"
                            f"Your previous submission failed QA review:\n{qa_verdict.findings}\n"
                            f"Specific issues: {qa_verdict.test_issues}\n\n"
                            f"Please return corrected JSON addressing every issue above."
                        )
                        raw_delta = llm_client.complete_json(
                            delta_system, delta_user_context,
                            label=f"function-{language}-{tag}-qa-retry{qa_attempt}",
                            max_tokens_override=settings.openai_max_tokens_test,
                        )
                        delta = validate_with_correction(
                            raw_delta, FunctionDeltaOutput, llm_client.complete_json,
                            delta_system, delta_user_context,
                            label=f"function-{language}-{tag}-qa-retry{qa_attempt}-validate",
                        )
                        # Re-validate compilation for the regenerated delta before another QA pass
                        test_files = self._inject_all_deltas(skeleton.files, {tag: delta}, language, skeleton)
                        if language == "java":
                            test_files = _fix_java_source_paths(test_files)
                            test_files = _fix_java_imports(test_files)
                        safe_test_files = sanitizer.sanitize_generated_files(test_files)
                        compile_validator.validate_compilation(safe_test_files, language)

                    tier_deltas[tier][tag] = delta
                    tier_qa_reports[tier][tag] = qa_verdict.model_dump()
                    cache_client.set(delta_cache_key, delta.model_dump_json(), expire=60 * 60 * 24)
                    log.info(f"ScaffoldGenerator: Phase 2b done — lang={language}, scenario={tag}")

            # Build manifest for this language
            manifest = self._build_manifest(challenge_name, language, design, active_tiers, tier_deltas, tier_qa_reports)
            all_manifests[language] = manifest

            # Upload gold masters + scaffold ZIPs
            gold_master_s3_refs: dict[str, str] = {}  # tier → s3:// URI, built as each upload succeeds
            gold_master_keys: dict[str, str] = {}  # tier → bucket-relative key, for hidden_test_key
            for tier in active_tiers:
                if tier in skipped_tiers:
                    continue
                skeleton = tier_skeletons[tier]
                deltas = tier_deltas[tier]
                tier_design = design.difficulty_tiers[tier]

                gold_master_files = self._inject_all_deltas(skeleton.files, deltas, language, skeleton)
                if language == "java":
                    gold_master_files = _fix_java_source_paths(gold_master_files)
                    gold_master_files = _fix_java_imports(gold_master_files)
                safe_gold_master = sanitizer.sanitize_generated_files(gold_master_files)
                test_hidden = {tag: d.test_hidden for tag, d in deltas.items()}

                # Every scenario's delta was only ever validated ALONE (Phase 2b, one delta
                # injected at a time) — this is the first point all N deltas for the tier are
                # combined, and the full hidden test suite actually runs (run_tests=True), not
                # just compiled. Two independently-valid deltas can still conflict once merged.
                # Patch incrementally on failure instead of hard-failing the whole job outright,
                # the same way the skeleton and per-delta stages already self-heal.
                _MAX_GOLD_MASTER_RETRIES = 2
                gold_master_attempt = 0
                while True:
                    try:
                        compile_validator.validate_compilation(safe_gold_master, language, run_tests=True)
                        break
                    except CompileValidationError as e:
                        # Try a Java-convention-only deterministic fix first — free (no
                        # LLM call, doesn't consume a retry attempt). Safe even for a test
                        # failure (run_tests=True): it only ever fires on a genuine
                        # constructor-arity compiler error pattern in the text, never on
                        # an assertion/runtime failure.
                        candidate_files, changed = _try_deterministic_fix(gold_master_files, str(e), language)
                        if changed:
                            try:
                                safe_candidate = sanitizer.sanitize_generated_files(candidate_files)
                                compile_validator.validate_compilation(safe_candidate, language, run_tests=True)
                                gold_master_files = candidate_files
                                safe_gold_master = safe_candidate
                                log.info(
                                    f"ScaffoldGenerator: gold master compile/test error resolved "
                                    f"deterministically (no LLM call needed) — tier={tier}"
                                )
                                continue
                            except CompileValidationError:
                                gold_master_files = candidate_files  # keep partial fix either way
                                safe_gold_master = sanitizer.sanitize_generated_files(candidate_files)

                        if gold_master_attempt >= _MAX_GOLD_MASTER_RETRIES:
                            error_msg = f"ScaffoldGenerator: compile/test validation failed tier={tier} lang={language}: {e}"
                            log.error(error_msg)
                            raise RuntimeError(error_msg)
                        gold_master_attempt += 1
                        hint = _classify_compile_error(str(e))
                        log.warning(
                            f"ScaffoldGenerator: gold master compile/test failed "
                            f"(attempt {gold_master_attempt}) — {hint}. Patching."
                        )
                        scenarios_json = json.dumps(tier_design["scenarios"], indent=2)
                        # Signature-only for Java: this is skeleton + every scenario's
                        # implementation combined — the largest of the three context dumps
                        # in this pipeline, and the most likely to blow past a TPM cap.
                        gold_master_context = (
                            _java_signature_summary(gold_master_files) if language == "java" else gold_master_files
                        )
                        patch_context = (
                            f"<tier>{tier.upper()}</tier>\n"
                            f"<scenarios>\n{scenarios_json}\n</scenarios>\n\n"
                            f"<current_gold_master_files>\n{json.dumps(gold_master_context, indent=2)}\n</current_gold_master_files>\n\n"
                            f"This is the FINAL assembled codebase for this tier (skeleton + "
                            f"every scenario's implementation, combined). It failed to "
                            f"compile/test:\n{e}\n\n"
                            f"How to fix: {hint}\n\n"
                            f"Do NOT regenerate the whole codebase. Return ONLY the new file(s) "
                            f"to add or the corrected content of the specific existing file(s) "
                            f"that need to change to fix this error — every other file in "
                            f"<current_gold_master_files> stays exactly as shown and must be "
                            f"omitted from your response. If a file needs to be deleted "
                            f"entirely (e.g. a genuine duplicate class), list its path in "
                            f"`remove_files` instead. "
                            f'Output JSON of the form: {{"files": {{"path/to/File.java": "..."}}, '
                            f'"remove_files": ["path/to/DeleteMe.java"]}}.'
                        )
                        raw_patch = llm_client.complete_json_cached(
                            skeleton_system,
                            patch_context,
                            label=f"goldmaster-{language}-{tier}-compile-retry",
                            max_tokens_override=settings.openai_max_tokens_impl,
                        )
                        patch: SkeletonPatchOutput = validate_with_correction(
                            raw_patch,
                            SkeletonPatchOutput,
                            lambda sys, usr, l=language, t=tier: llm_client.complete_json_cached(
                                sys, usr,
                                label=f"goldmaster-{l}-{t}-compile-retry-schema",
                                max_tokens_override=settings.openai_max_tokens_impl,
                            ),
                            skeleton_system,
                            patch_context,
                            label=f"goldmaster-{language}-{tier}-compile-retry-validate",
                        )
                        for removed_path in patch.remove_files:
                            gold_master_files.pop(removed_path, None)
                        gold_master_files.update(patch.files)
                        if language == "java":
                            gold_master_files = _fix_java_source_paths(gold_master_files)
                            gold_master_files = _fix_java_imports(gold_master_files)
                        safe_gold_master = sanitizer.sanitize_generated_files(gold_master_files)
                        log.info(
                            f"ScaffoldGenerator: gold master patched — lang={language}, "
                            f"tier={tier}, patched_files={list(patch.files.keys())}, "
                            f"removed_files={patch.remove_files}"
                        )

                try:
                    storage_client.upload_gold_master_from_dict(
                        safe_gold_master, test_hidden, manifest,
                        challenge_name, tier, language,
                    )
                    gold_master_s3_refs[tier] = f"s3://gold-masters/{language}/{challenge_name}-{tier}.zip"
                    gold_master_keys[tier] = f"{language}/{challenge_name}-{tier}.zip"
                except Exception as e:
                    error_msg = f"ScaffoldGenerator: gold master upload failed tier={tier} lang={language}: {e}"
                    log.error(error_msg)
                    raise RuntimeError(error_msg)

                safe_skeleton = sanitizer.sanitize_generated_files(skeleton.files)
                for scenario in tier_design["scenarios"]:
                    tag = scenario["scenario_tag"]
                    try:
                        scaffold_files = dict(safe_skeleton)
                        delta = tier_deltas[tier].get(tag)
                        if delta and delta.test_visible:
                            visible_path = _test_file_path(delta.test_visible)
                            if visible_path:
                                scaffold_files[visible_path] = delta.test_visible
                                log.info(f"ScaffoldGenerator: added visible test → {visible_path}")
                        zip_bytes = generator.generate_from_dict(scaffold_files, tag, manifest, language)
                        s3_key = f"{language}/{challenge_name}-{tag}.zip"
                        storage_client.upload_bytes(zip_bytes.getvalue(), settings.aws_s3_challenges_bucket, s3_key)
                        storage_client.export_scaffold_locally(zip_bytes.getvalue(), challenge_name, tag, language)
                        log.info(f"ScaffoldGenerator: uploaded scaffold → challenges/{s3_key}")
                    except Exception as e:
                        error_msg = f"ScaffoldGenerator: scaffold ZIP failed for scenario={tag} lang={language}: {e}"
                        log.error(error_msg)
                        raise RuntimeError(error_msg)

                if not failed_scaffolds:
                    try:
                        checkpoint_key = f"codegen:checkpoint:{challenge_name}:{design_fingerprint}:{language}:{tier}"
                        cache_client.set(checkpoint_key, "completed", expire=60 * 60 * 24)
                        log.info(f"ScaffoldGenerator: checkpoint written for tier={tier} lang={language}")
                    except Exception as e:
                        log.warning(f"ScaffoldGenerator: failed to write checkpoint tier={tier} lang={language}: {e}")

            manifest["goldMasterKeys"] = gold_master_keys

            # Phase 3 — Blueprints (language-level, after all tiers)
            if settings.enable_blueprint_generation and settings.enable_llm:
                try:
                    from services.blueprint import blueprint_service
                    blueprints = blueprint_service.generate_all_scenarios(
                        challenge_name, language, manifest,
                        gold_master_s3_refs=gold_master_s3_refs,
                    )
                    for bp in blueprints:
                        blueprint_service.dispatch(bp)  # best-effort: succeeds if problem row already exists
                        generated_blueprints[bp["problemId"]] = bp
                    log.info(f"ScaffoldGenerator: Generated {len(blueprints)} blueprints for lang={language}")
                except Exception as e:
                    log.error(f"ScaffoldGenerator: Blueprint generation failed for lang={language}: {e}")
                    failed_blueprints.append(language)

            log.info(f"ScaffoldGenerator: Phase 2 complete — language={language}")

        total_scenarios = sum(
            len(design.difficulty_tiers[t]["scenarios"]) for t in active_tiers
        )
        tok = llm_client._session_tokens
        log.info(
            f"ScaffoldGenerator: complete — challenge={challenge_name}, "
            f"languages={active_languages}, tiers={active_tiers}, "
            f"scenarios_per_tier={scenarios_per_tier}, total_scenarios={total_scenarios} | "
            f"session tokens — input: {tok['input']}, cached: {tok['cached']}, "
            f"output: {tok['output']} | "
            f"total cost: ${llm_client._session_cost:.4f}"
        )
        return {
            "challenge": challenge_name,
            "languages": active_languages,
            "tiers": active_tiers,
            "scenarios_per_tier": scenarios_per_tier,
            "manifests": all_manifests,
            "blueprints": generated_blueprints,
            "usage": {
                "input_tokens": tok["input"],
                "cached_tokens": tok["cached"],
                "output_tokens": tok["output"],
                "total_cost_usd": round(llm_client._session_cost, 4),
            },
            "warnings": {
                "failed_scaffolds": failed_scaffolds,
                "failed_blueprints": failed_blueprints,
            },
        }

    def _run_scenario_qa(
        self,
        language: str,
        tier: str,
        scenario: dict,
        delta: FunctionDeltaOutput,
    ) -> JudgeQAOutput:
        """Phase 4 — LLM-judge QA pass on a single generated scenario's delta.

        Checks difficulty calibration, time calibration, topic correctness, and
        test-case correctness/coverage (or rubric quality for judge-mode scenarios).
        """
        check_mode = scenario.get("check_mode", "deterministic")
        if check_mode == "non_deterministic":
            test_content = json.dumps(delta.rubric or [], indent=2)
            required_categories = "N/A — check_mode is non_deterministic, review the rubric instead"
        else:
            test_content = (
                f"=== test_hidden ===\n{delta.test_hidden}\n\n"
                f"=== test_visible ===\n{delta.test_visible}"
            )
            required_categories = ", ".join(_REQUIRED_TEST_CATEGORIES.get(tier, ()))

        qa_system = llm_client.load_prompt("judge_scenario_qa")
        qa_user_context = (
            f"<tier>{tier.upper()}</tier>\n"
            f"<topic>{scenario.get('topic', '')}</topic>\n"
            f"<allowed_topics>{','.join(_TOPICS)}</allowed_topics>\n"
            f"<scenario_title>{scenario['title']}</scenario_title>\n"
            f"<scenario_description>{scenario['description']}</scenario_description>\n"
            f"<strip_description>{scenario.get('strip_description', '')}</strip_description>\n"
            f"<bug_description>{scenario.get('bug_description', '')}</bug_description>\n"
            f"<gold_master_function>\n{delta.function_body}\n</gold_master_function>\n"
            f"<check_mode>{check_mode}</check_mode>\n"
            f"<required_test_categories>{required_categories}</required_test_categories>\n"
            f"<test_content>\n{test_content}\n</test_content>"
        )
        raw_qa = llm_client.complete_json(
            qa_system, qa_user_context,
            label=f"judge-qa-{language}-{scenario['scenario_tag']}",
        )
        return validate_with_correction(
            raw_qa, JudgeQAOutput, llm_client.complete_json,
            qa_system, qa_user_context,
            label=f"judge-qa-{language}-{scenario['scenario_tag']}-validate",
        )

    def _build_manifest(
        self,
        challenge_name: str,
        language: str,
        design: DesignOutput,
        active_tiers: list[str] | None = None,
        tier_deltas: dict[str, dict] | None = None,
        tier_qa_reports: dict[str, dict] | None = None,
    ) -> dict:
        tiers_to_use = active_tiers or list(_TIERS)
        tier_deltas = tier_deltas or {}
        tier_qa_reports = tier_qa_reports or {}
        scenarios = {}
        for tier in tiers_to_use:
            for scenario in design.difficulty_tiers[tier]["scenarios"]:
                tag = scenario["scenario_tag"]
                check_mode = scenario.get("check_mode", "deterministic")
                entry = {
                    "title": scenario["title"],
                    "description": scenario["description"],
                    "tier": tier,
                    "type": scenario.get("type", "implement"),
                    "check_mode": check_mode,
                    "topic": scenario.get("topic"),
                    "qa_report": tier_qa_reports.get(tier, {}).get(tag),
                }
                if check_mode == "non_deterministic":
                    delta = tier_deltas.get(tier, {}).get(tag)
                    entry["rubric"] = delta.rubric if delta else None
                scenarios[tag] = entry
        return {
            "challenge": challenge_name,
            "language": language,
            "scenarios": scenarios,
        }

    def _inject_all_deltas(
        self,
        skeleton_files: dict,
        deltas: dict,
        language: str,
        tier_skeleton: "SkeletonOutput | None" = None,
    ) -> dict:
        """Inject all N function implementations into the skeleton to produce the gold master.

        First attempts an exact string replace of the stub marker. If not found (LLM used a
        different throw message and the validator accepted via the level-2 fallback), falls back
        to regex-based function-body replacement using the stub_location metadata.
        """
        result = dict(skeleton_files)
        throw_template = _STUB_THROW.get(language, _STUB_THROW["node"])
        stub_locations = tier_skeleton.stub_locations if tier_skeleton else {}

        for tag, delta in deltas.items():
            throw_stmt = throw_template.format(tag=tag)
            injected = False
            target_file: str | None = None
            for filepath in list(result.keys()):
                if throw_stmt in result[filepath]:
                    result[filepath] = result[filepath].replace(throw_stmt, delta.function_body)
                    log.debug(f"Injected delta for {tag!r} into {filepath} (exact match)")
                    injected = True
                    target_file = filepath
                    break

            # Try DEBUG_SCENARIO marker (debug-type scenarios have broken code, not a stub throw)
            if not injected:
                debug_marker = f"DEBUG_SCENARIO: {tag}"
                for filepath in list(result.keys()):
                    if debug_marker in result[filepath]:
                        stub_loc = stub_locations.get(tag)
                        if stub_loc and stub_loc.function_name:
                            result[filepath] = _replace_function_body(
                                result[filepath],
                                stub_loc.function_name,
                                delta.function_body,
                                language,
                            )
                            log.debug(f"Injected debug fix for {tag!r} into {filepath} (DEBUG_SCENARIO marker)")
                            injected = True
                            target_file = filepath
                        break

            if not injected:
                stub_loc = stub_locations.get(tag)
                if stub_loc and stub_loc.file in result:
                    result[stub_loc.file] = _replace_function_body(
                        result[stub_loc.file],
                        stub_loc.function_name,
                        delta.function_body,
                        language,
                    )
                    log.warning(
                        f"Injected delta for {tag!r} via function-name fallback "
                        f"in {stub_loc.file!r} (function: {stub_loc.function_name!r})"
                    )
                    injected = True
                    target_file = stub_loc.file
                else:
                    log.error(
                        f"Could not inject delta for {tag!r}: "
                        f"stub_loc={stub_loc}, file not in skeleton"
                    )

            # Function-delta injection only ever touches the method body, never the file's
            # import section or field declarations — apply any imports/fields the delta
            # needs here, the only place that can.
            if injected and target_file and language == "java":
                if getattr(delta, "imports", None):
                    result[target_file] = _insert_imports(result[target_file], delta.imports)
                    log.debug(f"Inserted imports for {tag!r} into {target_file}: {delta.imports}")
                if getattr(delta, "fields", None):
                    result[target_file] = _insert_fields(result[target_file], delta.fields)
                    log.debug(f"Inserted fields for {tag!r} into {target_file}: {delta.fields}")
        return result


scaffold_generator = ScaffoldGenerator()
