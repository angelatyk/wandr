from behave import given, when, then

@given('a user has a defined current location')
def step_impl_defined_current_location(context):
    pass

@when('the route is generated')
def step_impl_route_generated(context):
    pass

@then('the current location should be the first stop on the route')
def step_impl_current_location_first_stop(context):
    pass

@given('a user has a finalized itinerary with multiple stops')
def step_impl_finalized_itinerary_multiple_stops(context):
    pass

@then('each stop should only be visited once during the trip')
def step_impl_stops_visited_once(context):
    pass
