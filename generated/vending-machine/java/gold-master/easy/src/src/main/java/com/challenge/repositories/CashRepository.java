package com.challenge.repositories;

import com.challenge.models.Cash;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CashRepository extends JpaRepository<Cash, Integer> {
    // Custom JPQL queries can be added here
}
