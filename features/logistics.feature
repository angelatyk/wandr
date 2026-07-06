Feature: Logistics & Routing Logic

  Scenario: Current location is the starting point of the route
    Given a user has a defined current location
    When the route is generated
    Then the current location should be the first stop on the route

  Scenario: Finalized stops are visited only once by default
    Given a user has a finalized itinerary with multiple stops
    When the route is generated
    Then each stop should only be visited once during the trip
