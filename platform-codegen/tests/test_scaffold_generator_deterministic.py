"""Regression tests for the deterministic (non-LLM) Java fixers in
services/scaffold_generator.py — each covers a recurring, purely mechanical
compile-error pattern discovered via live generation runs. None of these touch
business logic; see the fixers' own docstrings for the exact scope boundary.
"""
from services.scaffold_generator import (
    _fix_java_constructor_mismatch,
    _fix_java_imports,
    _fix_java_repository_method,
)


def test_constructor_mismatch_adds_all_args_constructor():
    error = (
        "constructor Connection in class com.challenge.models.Connection cannot be applied to given types;\n"
        "  required: no arguments\n"
        "  found: java.lang.Long,java.lang.Long\n"
    )
    files = {
        "src/main/java/com/challenge/models/Connection.java": (
            "package com.challenge.models;\n\n"
            "public class Connection {\n"
            "    private Long userId;\n"
            "    private Long connectionId;\n"
            "}\n"
        )
    }
    fixed = _fix_java_constructor_mismatch(files, error)
    content = fixed["src/main/java/com/challenge/models/Connection.java"]
    assert "@AllArgsConstructor" in content
    assert "@NoArgsConstructor" in content  # implicit no-arg ctor must be preserved


def test_jdk_import_added_for_bare_list_and_optional():
    files = {
        "src/main/java/com/challenge/controllers/JobController.java": (
            "package com.challenge.controllers;\n\n"
            "public class JobController {\n"
            "    List<String> tags;\n"
            "    Optional<String> name;\n"
            "}\n"
        )
    }
    fixed = _fix_java_imports(files)
    content = fixed["src/main/java/com/challenge/controllers/JobController.java"]
    assert "import java.util.List;" in content
    assert "import java.util.Optional;" in content


def test_repository_method_existsby_declared_from_caller_error():
    error = (
        "cannot find symbol\n"
        "  symbol:   method existsByUserIdAndConnectionId(java.lang.Long,java.lang.Long)\n"
        "  location: variable connectionRepository of type com.challenge.repositories.ConnectionRepository\n"
    )
    files = {
        "src/main/java/com/challenge/repositories/ConnectionRepository.java": (
            "package com.challenge.repositories;\n\n"
            "import com.challenge.models.Connection;\n"
            "import org.springframework.data.jpa.repository.JpaRepository;\n\n"
            "public interface ConnectionRepository extends JpaRepository<Connection, Long> {\n"
            "}\n"
        ),
        "src/main/java/com/challenge/models/Connection.java": (
            "package com.challenge.models;\n\n"
            "public class Connection {\n"
            "    private Long userId;\n"
            "    private Long connectionId;\n"
            "}\n"
        ),
    }
    fixed = _fix_java_repository_method(files, error)
    repo = fixed["src/main/java/com/challenge/repositories/ConnectionRepository.java"]
    assert "boolean existsByUserIdAndConnectionId(java.lang.Long userId, java.lang.Long connectionId);" in repo


def test_repository_method_findby_left_for_llm():
    error = (
        "cannot find symbol\n"
        "  symbol:   method findByUserId(java.lang.Long)\n"
        "  location: variable connectionRepository of type com.challenge.repositories.ConnectionRepository\n"
    )
    files = {
        "src/main/java/com/challenge/repositories/ConnectionRepository.java": (
            "package com.challenge.repositories;\n\n"
            "import com.challenge.models.Connection;\n"
            "import org.springframework.data.jpa.repository.JpaRepository;\n\n"
            "public interface ConnectionRepository extends JpaRepository<Connection, Long> {\n"
            "}\n"
        ),
        "src/main/java/com/challenge/models/Connection.java": (
            "package com.challenge.models;\n\npublic class Connection {\n    private Long userId;\n}\n"
        ),
    }
    fixed = _fix_java_repository_method(files, error)
    assert fixed == files  # findBy is ambiguous — must not fire


def test_secondary_top_level_type_extracted_to_own_public_file():
    """Live-discovered gap: an @Embeddable composite key declared as a second,
    package-private top-level class in the same file as its owning @Entity
    (e.g. `StockLevelId` in `StockLevel.java`) was invisible to the import map
    (which only registered the file's primary/filename-matching class), and
    even once imported would fail with a visibility error since it isn't public.

    Simply flipping the modifier in place is illegal Java (javac requires exactly
    one public top-level type per file, matching the filename) — the fix must
    split the secondary type into its own `StockLevelId.java`.
    """
    stock_level = (
        "package com.challenge.models;\n\n"
        "import jakarta.persistence.*;\n\n"  # wildcard import — must still be carried over
        "public class StockLevel {\n"
        "    private StockLevelId id;\n"
        "    private int quantity;\n"
        "}\n\n"
        "@Embeddable\n"
        "class StockLevelId {\n"
        "    private Long productId;\n"
        "    private Long binId;\n"
        "}\n"
    )
    inventory_service = (
        "package com.challenge.inventory;\n\n"
        "public class InventoryService {\n"
        "    public void transferStock() {\n"
        "        StockLevelId id = new StockLevelId();\n"
        "    }\n"
        "}\n"
    )
    files = {
        "src/main/java/com/challenge/models/StockLevel.java": stock_level,
        "src/main/java/com/challenge/inventory/InventoryService.java": inventory_service,
    }
    fixed = _fix_java_imports(files)
    svc = fixed["src/main/java/com/challenge/inventory/InventoryService.java"]
    model = fixed["src/main/java/com/challenge/models/StockLevel.java"]

    assert "import com.challenge.models.StockLevelId;" in svc
    assert "class StockLevelId" not in model  # split out, not left behind
    assert "public class StockLevel {" in model  # primary class untouched/still correct

    new_path = "src/main/java/com/challenge/models/StockLevelId.java"
    assert new_path in fixed
    new_file = fixed[new_path]
    assert "package com.challenge.models;" in new_file
    assert "import jakarta.persistence.*;" in new_file  # wildcard import carried over
    assert "public class StockLevelId" in new_file
    assert "@Embeddable" in new_file
    assert "private Long productId;" in new_file and "private Long binId;" in new_file


def test_secondary_type_same_package_usage_stays_package_private():
    stock_level = (
        "package com.challenge.models;\n\n"
        "public class StockLevel {\n"
        "    private int quantity;\n"
        "}\n\n"
        "class StockLevelId {\n"
        "    private Long productId;\n"
        "}\n"
    )
    other_in_same_package = (
        "package com.challenge.models;\n\n"
        "public class Other {\n"
        "    StockLevelId id;\n"
        "}\n"
    )
    files = {
        "src/main/java/com/challenge/models/StockLevel.java": stock_level,
        "src/main/java/com/challenge/models/Other.java": other_in_same_package,
    }
    fixed = _fix_java_imports(files)
    assert "public class StockLevelId" not in fixed["src/main/java/com/challenge/models/StockLevel.java"]


def test_ambiguous_secondary_type_name_left_untouched():
    foo1 = "package com.challenge.a;\n\npublic class Foo {\n}\n"
    foo2 = "package com.challenge.b;\n\nclass Foo {\n}\n"
    user = "package com.challenge.c;\n\npublic class User {\n    Foo f;\n}\n"
    files = {
        "src/main/java/com/challenge/a/Foo.java": foo1,
        "src/main/java/com/challenge/b/Foo.java": foo2,
        "src/main/java/com/challenge/c/User.java": user,
    }
    fixed = _fix_java_imports(files)
    assert fixed["src/main/java/com/challenge/b/Foo.java"] == foo2
