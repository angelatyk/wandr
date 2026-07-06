from behave import given, when, then
from ai.agents.profiler import _extract_named_fields, _persona_from_json_or_none, PROFILER_SYSTEM_PROMPT

@given('a user message "{message}"')
def step_impl_given_user_message(context, message):
    # Unescape newlines for multiline simulation
    context.user_message = message.replace("\\n", "\n")

@when('the profiler parses the fields')
def step_impl_when_profiler_parses(context):
    context.fields = _extract_named_fields(context.user_message)

@then('the profiler should require a transit preference clarification')
def step_impl_then_requires_clarification(context):
    has_required_fields = bool(context.fields.get("destination")) and bool(context.fields.get("duration")) and bool(context.fields.get("transit_preference"))
    assert not has_required_fields, "Expected required fields to be missing (specifically transit preference)"
    assert "transit_preference" not in context.fields, "Expected transit_preference to be absent"

@then('the profiler should require a destination clarification')
def step_impl_then_requires_destination_clarification(context):
    has_required_fields = bool(context.fields.get("destination")) and bool(context.fields.get("duration")) and bool(context.fields.get("transit_preference"))
    assert not has_required_fields, "Expected required fields to be missing (specifically destination)"
    assert "destination" not in context.fields, "Expected destination to be absent"

@then('the profiler should require a duration clarification')
def step_impl_then_requires_duration_clarification(context):
    has_required_fields = bool(context.fields.get("destination")) and bool(context.fields.get("duration")) and bool(context.fields.get("transit_preference"))
    assert not has_required_fields, "Expected required fields to be missing (specifically duration)"
    assert "duration" not in context.fields, "Expected duration to be absent"

@then('the destination should be "{destination}"')
def step_impl_then_destination(context, destination):
    assert context.fields.get("destination") == destination, f"Expected {destination}, got {context.fields.get('destination')}"

@then('the duration should be "{duration}"')
def step_impl_then_duration(context, duration):
    assert context.fields.get("duration") == duration, f"Expected {duration}, got {context.fields.get('duration')}"

@then('the transit preference should be "{preference}"')
def step_impl_then_transit_preference(context, preference):
    assert context.fields.get("transit_preference") == preference, f"Expected {preference}, got {context.fields.get('transit_preference')}"

@given("a raw JSON response '{json_str}'")
def step_impl_given_json(context, json_str):
    context.raw_json = json_str

@when("the profiler extracts the persona from JSON")
def step_impl_extract_persona(context):
    context.persona = _persona_from_json_or_none(context.raw_json)

@then('the persona type should be "{persona_type}"')
def step_impl_persona_type(context, persona_type):
    assert context.persona.type == persona_type, f"Expected {persona_type}, got {context.persona.type}"

@then('the pace should be "{pace}"')
def step_impl_pace(context, pace):
    assert context.persona.pace == pace, f"Expected {pace}, got {context.persona.pace}"

@then('the budget should be "{budget}"')
def step_impl_budget(context, budget):
    assert context.persona.budget == budget, f"Expected {budget}, got {context.persona.budget}"

@given('the profiler agent is initialized')
def step_impl_profiler_initialized(context):
    pass

@then('the profiler system prompt should contain instructions to reject unrelated topics')
def step_impl_profiler_rejects_unrelated(context):
    assert "unrelated to travel" in PROFILER_SYSTEM_PROMPT, "Expected prompt to instruct rejecting non-travel topics"
