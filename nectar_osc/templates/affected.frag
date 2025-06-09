{% if affected -%}
<br>
<br>
<h2>Affected Instances</h2>
<table>
  <thead>
    <tr>
      <th style="padding: 0.5em; border: 1px solid black;">ID</th>
      <th style="padding: 0.5em; border: 1px solid black;">IP address</th>
      <th style="padding: 0.5em; border: 1px solid black;">Name</th>
      <th style="padding: 0.5em; border: 1px solid black;">Project</th>
    </tr>
  </thead>
  <tbody>
    {% for instance in instances -%}
    <tr>
      <td style="padding: 0.5em; border: 1px solid black;">
        {{ instance.id }}
      </td>
      <td style="padding: 0.5em; border: 1px solid black;">
        {{ ','.join(instance.addresses) }}
      </td>
      <td style="padding: 0.5em; border: 1px solid black;">
        {{ instance.name }}
      </td>
      <td style="padding: 0.5em; border: 1px solid black;">
        {{ instance.project_name }}
      </td>
    </tr>
    {% endfor -%}
  </tbody>
</table>
<br>
<br>
{% endif %}
