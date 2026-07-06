Feature: Profiler & Persona Logic

  Scenario: Profiler parses valid trip details
    Given a user message "Destination: Tokyo\nDuration: 2 days\nTransit preference: walking"
    When the profiler parses the fields
    Then the destination should be "Tokyo"
    And the duration should be "2 days"
    And the transit preference should be "walking"

  Scenario: Profiler rejects missing transit preference
    Given a user message "I want to explore Tokyo for 2 days"
    When the profiler parses the fields
    Then the profiler should require a transit preference clarification

  Scenario: Profiler rejects missing destination
    Given a user message "I have 2 days and want to walk around"
    When the profiler parses the fields
    Then the profiler should require a destination clarification

  Scenario: Profiler rejects missing duration
    Given a user message "I want to explore Tokyo and prefer walking"
    When the profiler parses the fields
    Then the profiler should require a duration clarification

  Scenario: Profiler defaults to tourist persona when type is missing
    Given a raw JSON response '{"destination": "Toronto", "duration": "2 hours", "transit_preference": "walking"}'
    When the profiler extracts the persona from JSON
    Then the persona type should be "tourist"

  Scenario: Profiler defaults to moderate pace and mid budget when missing
    Given a raw JSON response '{"destination": "Tokyo", "duration": "3 days", "transit_preference": "transit"}'
    When the profiler extracts the persona from JSON
    Then the pace should be "moderate"
    And the budget should be "mid"

  Scenario: Profiler prompt restricts non-travel topics
    Given the profiler agent is initialized
    Then the profiler system prompt should contain instructions to reject unrelated topics
