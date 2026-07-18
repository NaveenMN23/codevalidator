# Java pom.xml Template Strategy

## Problem

The `implement_skeleton_java.mdx` prompt previously instructed the LLM to generate `pom.xml`
as part of the skeleton output. This introduced three failure modes:

1. **Version hallucination** — the LLM generated different Spring Boot parent versions across
   runs (`3.1.0`, `3.2.0`, `3.3.0`), causing inconsistent builds.
2. **Wrong import packages** — root cause of the `@LocalServerPort` compilation bug seen in
   ECS task execution. The LLM used `org.springframework.boot.web.server.LocalServerPort`
   instead of `org.springframework.boot.test.web.server.LocalServerPort` (correct for
   Spring Boot 3.x) because it had no anchor to a specific version.
3. **Missing or extra dependencies** — LLM could omit `spring-retry` on HARD tier challenges
   or add unused deps.

## Solution

A pinned `pom.xml` template lives at `platform-codegen/templates/java/pom.xml`.

Phase 2a of `ScaffoldGenerator` injects this template into `skeleton.files["pom.xml"]`
immediately after the LLM call, overwriting whatever the LLM generated (if anything).
The prompt is updated to explicitly tell the LLM not to generate `pom.xml`.

## Template

**Location:** `platform-codegen/templates/java/pom.xml`

**Parent:** `spring-boot-starter-parent` `3.2.5`

**Java version:** `21`

### Dependencies

| Dependency | Scope | Purpose |
|---|---|---|
| `spring-boot-starter-web` | compile | REST controllers |
| `spring-boot-starter-data-jpa` | compile | JPA / Hibernate |
| `h2` | test | In-memory DB for JUnit tests |
| `flyway-core` | compile | DB migrations |
| `lombok` | compile | `@Getter` / `@Setter` on entities |
| `spring-boot-starter-test` | test | JUnit 5, AssertJ, MockMvc |
| `spring-retry` | compile | HARD tier retry logic |
| `spring-aspects` | compile | Required by spring-retry AOP |
| `spring-boot-starter-data-redis` | compile | HARD tier Redis use cases |

All versions are resolved via the Spring Boot 3.2.5 BOM — no explicit versions needed.

## Prompt Changes (`implement_skeleton_java.mdx`)

- `pom.xml` removed from the Output Schema example.
- Implementation Requirement #4 (previously "generate pom.xml") replaced with an explicit
  import anchor rule:
  > This project uses Spring Boot **3.2.5**. Use
  > `org.springframework.boot.test.web.server.LocalServerPort`
  > (NOT `org.springframework.boot.web.server.LocalServerPort`).

## Code Change (`scaffold_generator.py`)

```python
# platform-codegen/templates/java/pom.xml is read once at module level
_JAVA_POM_TEMPLATE = (
    Path(__file__).parent.parent / "templates" / "java" / "pom.xml"
).read_text()

# In Phase 2a, after validate_with_correction() returns the SkeletonOutput:
if language == "java":
    skeleton.files["pom.xml"] = _JAVA_POM_TEMPLATE
```

The injection happens before:
- `compile_validator.validate_compilation` — so the correct deps are available during
  `mvn test-compile`
- `storage_client.upload_gold_master_from_dict` — so the gold master ZIP contains the
  pinned pom.xml
- Scaffold ZIPs uploaded to S3 — so `DockerImageService` extracts the pinned pom.xml
  when pre-baking Maven deps into the ECR image

## Downstream Impact

`DockerImageService` is unchanged. It extracts the file named `pom.xml` from the scaffold
ZIP (`DockerfileTemplates.depFileName("java") == "pom.xml"`) and now gets the pinned
template version, which is exactly what should be baked into the Docker image.
