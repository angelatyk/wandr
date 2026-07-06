Feature: Itinerary & Duration Logic

  Scenario: Trip duration parsing for a short outing
    Given a user requests a trip with duration "7 hours"
    When the duration is parsed
    Then the resulting day count should be 1
    And the parsed duration should be flagged as a single outing
    And the total hours should be 7

  Scenario: Trip duration parsing for a multi-day trip
    Given a user requests a trip with duration "3 days"
    When the duration is parsed
    Then the resulting day count should be 3
    And the parsed duration should not be a single outing
    And the total hours should be 72

  Scenario: Itinerary generates enough options for curation
    Given a user requests a trip with duration "2 hours"
    When the duration is parsed
    And the max options per day is calculated
    Then the max options per day should be at least 5

  Scenario: Itinerary provides a mix of short and long stops
    Given the itinerary agent researches options
    When the options are generated
    Then the options should include stops that use up the entire duration
    And the options should include shorter stops for a mix of choices

  Scenario: Itinerary regenerates with user refinements
    Given a user refines the itinerary with "I want more historical sites"
    When the itinerary agent reruns
    Then the new options should include the user's refinement
