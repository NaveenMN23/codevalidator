"""Tests for _java_signature_summary — the token-cheap Java context builder used to
avoid dumping full file bodies into every LLM prompt. Built after a live 'Request too
large' 429 (input tokens exceeding the account's per-minute rate limit) was traced to
full skeleton/gold-master dumps at scaffold_generator.py's three retry-context sites.
"""
from services.llm import _count_tokens
from services.scaffold_generator import _java_signature_summary

HOTEL_ENTITY = """package com.challenge.domain.entities;

import jakarta.persistence.*;
import java.util.List;

@Entity
public class Hotel {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String name;

    public Hotel() {
    }

    public Long getId() {
        return this.id;
    }

    @Transactional
    public void addRoom(Room room) {
        if (room == null) {
            throw new IllegalArgumentException("room is null");
        }
        for (int i = 0; i < 3; i++) {
            System.out.println(i);
        }
    }
}
"""

USE_CASE = """package com.challenge.application.usecases;

public class CancelReservationUseCase {
    private final ReservationRepositoryPort repo;

    public CancelReservationUseCase(ReservationRepositoryPort repo) {
        this.repo = repo;
    }

    public void execute(Long id) {
        Reservation r = repo.findById(id).orElseThrow(() -> new RuntimeException("not found"));
        repo.delete(r);
    }
}
"""


def _sample_files():
    return {
        "src/main/java/com/challenge/domain/entities/Hotel.java": HOTEL_ENTITY,
        "src/main/java/com/challenge/application/usecases/CancelReservationUseCase.java": USE_CASE,
        "src/main/java/com/challenge/application/usecases/CreateReservationUseCase.java": USE_CASE,
        "README-hard-cancellation-fee.md": "# some doc\n" * 200,
        "pom.xml": "<project>...</project>\n" * 50,
    }


def test_drops_readme_and_pom():
    summarized = _java_signature_summary(_sample_files())
    assert "README-hard-cancellation-fee.md" not in summarized
    assert "pom.xml" not in summarized


def test_keep_full_passes_through_untouched():
    stub_path = "src/main/java/com/challenge/application/usecases/CreateReservationUseCase.java"
    summarized = _java_signature_summary(_sample_files(), keep_full=frozenset({stub_path}))
    assert summarized[stub_path] == USE_CASE


def test_signatures_fields_imports_preserved_bodies_stripped():
    summarized = _java_signature_summary(_sample_files())
    hotel = summarized["src/main/java/com/challenge/domain/entities/Hotel.java"]

    assert "package com.challenge.domain.entities;" in hotel
    assert "import java.util.List;" in hotel
    assert "@Entity" in hotel
    assert "public class Hotel {" in hotel
    assert "@Id" in hotel and "private Long id;" in hotel
    assert "private String name;" in hotel
    assert "public Hotel()" in hotel
    assert "public Long getId()" in hotel
    assert "@Transactional" in hotel
    assert "public void addRoom(Room room)" in hotel
    assert "implementation omitted for context" in hotel

    # Actual implementation detail must be gone
    assert "IllegalArgumentException" not in hotel
    assert "System.out.println" not in hotel
    assert "return this.id" not in hotel


def test_use_case_constructor_and_method_signatures_preserved():
    summarized = _java_signature_summary(_sample_files())
    use_case = summarized["src/main/java/com/challenge/application/usecases/CancelReservationUseCase.java"]

    assert "private final ReservationRepositoryPort repo;" in use_case
    assert "public CancelReservationUseCase(ReservationRepositoryPort repo)" in use_case
    assert "public void execute(Long id)" in use_case
    assert "findById" not in use_case
    assert "repo.delete(r)" not in use_case


def test_interface_method_declarations_pass_through_unchanged():
    port = (
        "package com.challenge.application.ports;\n\n"
        "public interface ReservationRepositoryPort {\n"
        "    Reservation findById(Long id);\n"
        "    void delete(Reservation r);\n"
        "}\n"
    )
    summarized = _java_signature_summary({"src/main/java/com/challenge/application/ports/ReservationRepositoryPort.java": port})
    out = list(summarized.values())[0]
    assert out == port  # no bodies to strip — must be byte-identical


def test_reduces_token_count_substantially():
    files = _sample_files()
    del files["README-hard-cancellation-fee.md"]
    del files["pom.xml"]
    before = sum(_count_tokens(c) for c in files.values())
    summarized = _java_signature_summary(files)
    after = sum(_count_tokens(c) for c in summarized.values())
    assert after < before
