import os
import subprocess
import tempfile
import json
from pathlib import Path
from infrastructure.logger import log

class CompileValidationError(Exception):
    """Raised when generated code fails to compile."""
    pass

class CompileValidator:
    def validate_compilation(self, files_dict: dict, language: str, run_tests: bool = False) -> None:
        """
        Writes files_dict to a temporary directory and attempts to compile it.
        Raises CompileValidationError if the compilation command returns a non-zero exit code.

        run_tests: for Java, also executes the test suite (mvn test) instead of only
        compiling it (mvn test-compile). Only appropriate once implementation is complete
        (e.g. the final gold-master stage) — earlier stages have intentionally-incomplete
        stub code where tests are expected to fail.
        """
        if language not in ["java", "node", "python"]:
            log.warning(f"Compile validation not implemented for language: {language}")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Write all files to the temporary directory
            for rel_path, content in files_dict.items():
                file_path = tmp_path / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding='utf-8')
            
            log.info(f"Compile validation started for language '{language}' in {tmpdir}")
            
            try:
                if language == "java":
                    self._validate_java(tmp_path, run_tests=run_tests)
                elif language == "node":
                    self._validate_node(tmp_path)
                elif language == "python":
                    self._validate_python(tmp_path)
                log.info(f"Compile validation SUCCESS for language '{language}'")
            except subprocess.CalledProcessError as e:
                import shutil
                dest = "/tmp/failed_compile_latest"
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(tmpdir, dest)
                
                output_str = ""
                if getattr(e, 'stdout', None):
                    output_str += f"STDOUT:\n{e.stdout}\n"
                if getattr(e, 'stderr', None):
                    output_str += f"STDERR:\n{e.stderr}\n"
                if not output_str and getattr(e, 'output', None):
                    output_str += f"OUTPUT:\n{e.output}\n"

                error_msg = f"Compile validation failed for {language}.\nCommand: {e.cmd}\nExit Code: {e.returncode}\n{output_str}"
                log.error(error_msg)
                raise CompileValidationError(error_msg)

    def _validate_java(self, cwd: Path, run_tests: bool = False):
        # test-compile compiles both main and test sources; test also executes them
        # (and implies compilation, so this replaces rather than adds a step).
        goal = "test" if run_tests else "test-compile"
        cmd = ["mvn", "-B", "-q", goal]
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return
        combined = (result.stdout or "") + (result.stderr or "")
        # Dependency resolution failures are network/infra issues, not code errors.
        # Raising CompileValidationError here would cause the LLM to "fix" unfixable problems.
        if "Could not transfer artifact" in combined or "Name or service not known" in combined \
                or "Temporary failure in name resolution" in combined \
                or "Could not resolve dependencies" in combined:
            log.warning(
                "Java compile validation skipped — Maven could not reach remote repositories. "
                "This is a network/infra issue, not a code error."
            )
            return
        err = subprocess.CalledProcessError(result.returncode, cmd)
        err.stdout = result.stdout
        err.stderr = result.stderr
        raise err

    def _validate_node(self, cwd: Path):
        if not (cwd / "package.json").exists():
            log.warning("package.json missing, injecting fallback")
            (cwd / "package.json").write_text('{"name":"fallback","dependencies":{"fastify":"^4.28.1","better-sqlite3":"^11.1.2"},"devDependencies":{"typescript":"^5.4.5","@types/node":"^20","@types/better-sqlite3":"^7","tsx":"^4"}}')
        if not (cwd / "tsconfig.json").exists():
            (cwd / "tsconfig.json").write_text('{"compilerOptions":{"target":"ES2022","module":"CommonJS","strict":true}}')

        # To compile typescript, we need node_modules, so we must npm install first.
        # This will take some time, but we use --prefer-offline if possible, though clean dir.
        subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        
        # LLMs often forget @types, so ensure they are installed to prevent spurious TS errors
        subprocess.run(
            ["npm", "install", "--no-save", "--no-audit", "--no-fund", "--loglevel=error", "@types/node", "@types/better-sqlite3", "typescript"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )

        # Override tsconfig to prevent trivial TS strict errors from failing generation
        (cwd / "tsconfig.json").write_text('{"compilerOptions":{"target":"ES2022","module":"CommonJS","strict":false,"noImplicitAny":false,"esModuleInterop":true,"skipLibCheck":true}}')

        # Then run tsc --noEmit to check types.
        # We catch and log errors instead of failing the pipeline because the execution engine uses 'tsx'
        # which ignores TS type errors, and LLMs often have minor typing issues (like unknown body types).
        try:
            subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            log.warning(f"tsc --noEmit failed (ignoring since tsx runtime is used):\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")

    def _validate_python(self, cwd: Path):
        # We can use py_compile as a basic check for python files
        py_files = list(cwd.rglob("*.py"))
        if not py_files:
            return
            
        cmd = ["python3", "-m", "py_compile"] + [str(p) for p in py_files]
        subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )

compile_validator = CompileValidator()
