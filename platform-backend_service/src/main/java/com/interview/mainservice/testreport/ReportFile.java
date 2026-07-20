package com.interview.mainservice.testreport;

/** Raw report file as read back from the sandbox — mirrors sandbox-runner's ReportFile struct. */
public record ReportFile(String path, String content) {
}
