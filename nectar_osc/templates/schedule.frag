<br>
<br>
{% macro human_time(ts) -%}
{{ ts.strftime('%-I:%M') }}{{ ts.strftime('%p') | lower }} {{ ts.strftime('%A %-d %B %Y') }} {{ ts.strftime('%Z') }}
{%- endmacro -%}
<p>
  <b>Duration:</b> {% if days %}{{ days }} day{{ 's' if days != 1 }}{% if hours %} {% endif %}{% endif %}{% if hours or not days %}{{ hours }} hour{{ 's' if hours != 1 }}{% endif %}<br>
  <b>Start time:</b> {{ human_time(start_ts) }}<br>
  <b>End time:</b> {{ human_time(end_ts) }}<br>
</p>
