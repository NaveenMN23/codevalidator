package com.interview.admin.controller;

import com.interview.admin.dto.PageResponse;
import com.interview.admin.dto.UserResponse;
import com.interview.admin.service.UserManagementService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/admin/users")
@CrossOrigin(origins = "*")
public class UserAdminController {

    private final UserManagementService userService;

    public UserAdminController(UserManagementService userService) {
        this.userService = userService;
    }

    @GetMapping
    public ResponseEntity<PageResponse<UserResponse>> listUsers(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(userService.listUsers(page, size));
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserResponse> getUser(@PathVariable UUID id) {
        return ResponseEntity.ok(userService.getUser(id));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteUser(@PathVariable UUID id) {
        userService.deleteUser(id);
        return ResponseEntity.noContent().build();
    }
}
