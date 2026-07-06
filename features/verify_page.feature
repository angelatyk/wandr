Feature: Verify Page Time Calculation & Confirmation

  Scenario: User is prompted to confirm if selected options exceed total time
    Given a user has a specified duration of "4 hours"
    And the user selects options totaling "5 hours" including travel
    When the user clicks Finalize Itinerary
    Then a confirmation modal should appear asking to proceed with exceeded time

  Scenario: Overhead time is calculated for multi-day trips
    Given a user has a specified duration of "2 days"
    When the user clicks Finalize Itinerary
    Then overhead time for resting and eating should be included in the total time

  Scenario: Overhead time is not calculated for short outings
    Given a user has a specified duration of "4 hours"
    When the user clicks Finalize Itinerary
    Then overhead time for resting and eating should not be included in the total time

  Scenario: User reduces options when time is exceeded
    Given a user is prompted with an exceeded time confirmation
    When the user rejects the confirmation
    Then the user should remain on the Verify Page to reduce options
