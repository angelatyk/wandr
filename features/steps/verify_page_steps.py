from behave import given, when, then

@given('a user has a specified duration of "{duration}"')
def step_impl_specified_duration(context, duration):
    pass

@given('the user selects options totaling "{total}" including travel')
def step_impl_selects_totaling(context, total):
    pass

@when('the user clicks Finalize Itinerary')
def step_impl_clicks_finalize(context):
    pass

@then('a confirmation modal should appear asking to proceed with exceeded time')
def step_impl_confirmation_modal(context):
    pass

@then('overhead time for resting and eating should be included in the total time')
def step_impl_overhead_time(context):
    pass

@then('overhead time for resting and eating should not be included in the total time')
def step_impl_no_overhead_time(context):
    pass

@given('a user is prompted with an exceeded time confirmation')
def step_impl_prompted_confirmation(context):
    pass

@when('the user rejects the confirmation')
def step_impl_rejects_confirmation(context):
    pass

@then('the user should remain on the Verify Page to reduce options')
def step_impl_remain_verify_page(context):
    pass
