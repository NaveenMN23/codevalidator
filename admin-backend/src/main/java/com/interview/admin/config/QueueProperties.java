package com.interview.admin.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.queues")
public class QueueProperties {

    private String codegenRequest;
    private String codegenResults;

    public String getCodegenRequest() { return codegenRequest; }
    public void setCodegenRequest(String codegenRequest) { this.codegenRequest = codegenRequest; }

    public String getCodegenResults() { return codegenResults; }
    public void setCodegenResults(String codegenResults) { this.codegenResults = codegenResults; }
}
