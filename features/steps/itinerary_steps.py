from behave import given, when, then
from ai.models.duration import parse_trip_duration, max_options_per_day
from ai.agents.itinerary import _build_duration_rules, _build_refinement_section

@given('a user requests a trip with duration "{duration}"')
def step_impl_given_duration(context, duration):
    context.request_duration = duration

@when('the duration is parsed')
def step_impl_when_parsed(context):
    context.parsed_duration = parse_trip_duration(context.request_duration)

@then('the resulting day count should be {day_count:d}')
def step_impl_then_day_count(context, day_count):
    assert context.parsed_duration.day_count == day_count, f"Expected {day_count}, got {context.parsed_duration.day_count}"

@then('the parsed duration should be flagged as a single outing')
def step_impl_then_single_outing(context):
    assert context.parsed_duration.is_single_outing is True, "Expected is_single_outing to be True"

@then('the parsed duration should not be a single outing')
def step_impl_then_not_single_outing(context):
    assert context.parsed_duration.is_single_outing is False, "Expected is_single_outing to be False"

@then('the total hours should be {total_hours:d}')
def step_impl_then_total_hours(context, total_hours):
    assert context.parsed_duration.total_hours == total_hours, f"Expected {total_hours}, got {context.parsed_duration.total_hours}"

@when('the max options per day is calculated')
def step_impl_when_max_options(context):
    context.max_options = max_options_per_day(context.parsed_duration, context.parsed_duration.day_count)

@then('the max options per day should be at least {min_options:d}')
def step_impl_then_max_options(context, min_options):
    assert context.max_options >= min_options, f"Expected at least {min_options}, got {context.max_options}"

@given('the itinerary agent researches options')
def step_impl_itinerary_researches(context):
    # Mocking a parsed duration for the generation steps
    context.parsed_duration = parse_trip_duration("3 days")

@when('the options are generated')
def step_impl_options_generated(context):
    # Test the prompt engineering logic that controls the LLM
    context.prompt_rules = _build_duration_rules(context.parsed_duration)

@then('the options should include stops that use up the entire duration')
def step_impl_options_entire_duration(context):
    assert "total time can exceed the duration" in context.prompt_rules or "CAN exceed the specified duration" in context.prompt_rules, "Expected duration usage rules in prompt"

@then('the options should include shorter stops for a mix of choices')
def step_impl_options_mix(context):
    assert "Include a mix of primary attractions and **short stops**" in context.prompt_rules, "Expected short stop instruction in prompt"

@given('a user refines the itinerary with "{refinement}"')
def step_impl_user_refines(context, refinement):
    context.refinement_text = refinement

@when('the itinerary agent reruns')
def step_impl_itinerary_reruns(context):
    context.refinement_prompt = _build_refinement_section(context.refinement_text)

@then('the new options should include the user\'s refinement')
def step_impl_options_include_refinement(context):
    assert context.refinement_text in context.refinement_prompt, "Expected refinement text to be injected into the prompt"
