# SimplyBook Iframe Widget Reference

## Purpose

This reference captures the live SimplyBook iframe widget designer configuration inspected at:

- `https://simplydemo.secure.simplybook.me/v2/design/widget/type/iframe`
- Booking host: `https://simplydemo.simplybook.me`

The implementation should use the existing local `widget.js` as the host-side loader and lifecycle controller. The widget itself remains an iframe application.

## Confirmed architecture

```text
Host website
  -> local widget.js
  -> iframe booking application
  -> postMessage lifecycle and dynamic sizing
  -> FastAPI booking-form resolver
  -> relationship resolver and scheduling engine
```

The stored booking-form configuration is authoritative for booking flow, module order, enabled modules, relationship rules and provider-selection behaviour. Widget parameters control presentation, iframe behaviour and optional initial selections.

## Supported widget modes visible in the designer

- Iframe widget
- Package widget
- Membership widget
- Booking button
- Contact widget
- Reviews widget
- Smart widget (Beta)
- AI Chat widget (Beta)

This project should implement the iframe widget path.

## Theme keys

The live designer exposed these theme keys:

- `space`
- `creative`
- `minimal`
- `dainty`
- `inspiration`
- `air`
- `emeri`
- `bookingtroll`
- `classic`
- `hugo`
- `belle`
- `concise`
- `simple_beauty_theme`
- `blur`
- `skittish`
- `tender`
- `default`
- `adacompliant`

The selected demo theme was `minimal`.

## Calendar layout values

The `timeline` setting accepts:

| Label | Value |
|---|---|
| Flexible | `flexible` |
| Modern | `modern` |
| Flexible weekly | `flexible_week` |
| Slots weekly | `modern_week` |
| Flexible Provider | `flexible_provider` |
| Weekly classes | `grid_week` |
| Daily classes | `classes_plugin` |

The demo selection was `classes_plugin`.

## Datepicker values

The `datepicker` setting accepts:

| Label | Value |
|---|---|
| Top calendar | `top_calendar` |
| Inline datepicker | `inline_datepicker` |

The demo selection was `top_calendar`.

## Additional timeline display

`timeline_modern_display` accepts:

- `as_slots`
- `as_table`

## Theme settings

The generated widget configuration used these `theme_settings` keys:

- `timeline_show_end_time`
- `timeline_modern_display`
- `hide_company_label`
- `timeline_hide_unavailable`
- `hide_past_days`
- `sb_base_color`
- `btn_color_1`
- `link_color`
- `display_item_mode`
- `body_bg_color`
- `sb_review_image`
- `dark_font_color`
- `light_font_color`
- `sb_company_label_color`
- `hide_img_mode`
- `sb_busy`
- `sb_available`

### Demo values

```json
{
  "timeline_show_end_time": "1",
  "timeline_modern_display": "as_slots",
  "hide_company_label": "0",
  "timeline_hide_unavailable": "1",
  "hide_past_days": "0",
  "sb_base_color": "#e49092",
  "btn_color_1": "#f5a778,#e6938f,#e28c96",
  "link_color": "#e49092",
  "display_item_mode": "block",
  "body_bg_color": "#ffffff",
  "sb_review_image": "",
  "dark_font_color": "#2b212b",
  "light_font_color": "#ffffff",
  "sb_company_label_color": "#e49092",
  "hide_img_mode": "0",
  "sb_busy": "#aaa6aa",
  "sb_available": "#2b212b"
}
```

`btn_color_1` is a comma-separated three-colour gradient value.

## Other visible settings

- Show only available time: `timeline_hide_unavailable`
- Hide unavailable days on calendar: `hide_past_days`
- Show end time: `timeline_show_end_time`
- Hide company title: `hide_company_label`
- Display item mode: `block` or `list`
- Hide images on booking steps: `hide_img_mode`
- Right-to-left layout: `is_rtl`
- Clear session on each widget initialization: `clear_session`
- Allow switching to ADA-compliant theme: `allow_switch_to_ada`

## Predefined values

The iframe widget can be initialized with predefined:

- location
- category
- service
- provider
- client details
- arbitrary custom field values

The generated root shape is:

```json
{
  "app_config": {
    "clear_session": 0,
    "allow_switch_to_ada": 0,
    "predefined": []
  }
}
```

The designer also documents this richer client/custom-field structure:

```js
predefined: {
  client: {
    name: "Predefined client name",
    email: "Predefined client email",
    phone: "Predefined client phone"
  },
  fields: {
    "field-id": "value"
  }
}
```

Date field values use `yyyy-mm-dd`.

## Generated main widget code

```html
<script src="//widget.simplybook.me/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
  var widget = new SimplybookWidget({
    widget_type: "iframe",
    url: "https://simplydemo.simplybook.me",
    theme: "minimal",
    theme_settings: {
      timeline_show_end_time: "1",
      timeline_modern_display: "as_slots",
      hide_company_label: "0",
      timeline_hide_unavailable: "1",
      hide_past_days: "0",
      sb_base_color: "#e49092",
      btn_color_1: "#f5a778,#e6938f,#e28c96",
      link_color: "#e49092",
      display_item_mode: "block",
      body_bg_color: "#ffffff",
      sb_review_image: "",
      dark_font_color: "#2b212b",
      light_font_color: "#ffffff",
      sb_company_label_color: "#e49092",
      hide_img_mode: "0",
      sb_busy: "#aaa6aa",
      sb_available: "#2b212b"
    },
    timeline: "classes_plugin",
    datepicker: "top_calendar",
    is_rtl: false,
    app_config: {
      clear_session: 0,
      allow_switch_to_ada: 0,
      predefined: []
    }
  });
</script>
```

## Generated container-specific alternative

```html
<div id="widget-container"></div>
<script type="text/javascript">
  (function (w, d, s) {
    var script = d.createElement(s);
    script.async = true;
    script.src = "//widget.simplybook.me/v2/widget/widget.js";
    script.onload = function () {
      new SimplybookWidget({
        widget_type: "iframe",
        url: "https://simplydemo.simplybook.me",
        theme: "minimal",
        theme_settings: {},
        timeline: "classes_plugin",
        datepicker: "top_calendar",
        is_rtl: false,
        app_config: {
          clear_session: 0,
          allow_switch_to_ada: 0,
          predefined: []
        },
        container_id: "widget-container"
      });
    };
    d.head.appendChild(script);
  })(window, document, "script");
</script>
```

For this project, replace the remote script source with the locally served existing `widget.js`.

## Live iframe URL pattern

The designer preview used this shape:

```text
https://simplydemo.simplybook.me/v2/
  ?preview=1
  &theme_id=47
  &widget-type=iframe
  &is_rtl=0
  &timeline=classes_plugin
  &datepicker=top_calendar
  #book
```

The project should generate its iframe URL from the stored widget configuration and booking-form identity rather than hard-coding the SimplyBook host.

## Responsive preview behaviour

The designer provides:

- phone preview
- tablet preview
- desktop preview
- front/side orientation controls
- landscape mode
- rotation
- narrow mode
- QR preview on a physical device

The host `widget.js` should retain dynamic iframe height handling, modal expansion/collapse and focus restoration through `postMessage`.

## Implementation rules for this project

1. Keep the existing root `widget.js` rather than introducing a second widget loader.
2. Use `widget_type: "iframe"`.
3. Treat `container_id` as required for multiple or React-mounted widget instances.
4. Keep presentation settings separate from booking-flow configuration.
5. Resolve booking form, module order, optional modules, presets and relationship constraints through FastAPI.
6. Permit predefined location, category, service and provider as initial constraints, not as replacements for relationship validation.
7. Support `clear_session`, RTL and ADA switching.
8. Preserve `postMessage` lifecycle handling for readiness, resizing, modal state, step changes, scrolling and focus restoration.
9. Ensure the iframe has an accessible title and a stable container.
10. Avoid loading the widget script more than once per page.

## Recommended project configuration shape

```ts
export interface IframeWidgetConfig {
  containerId: string;
  bookingFormSlug: string;
  widgetType: "iframe";
  theme: string;
  timeline: string;
  datepicker: "top_calendar" | "inline_datepicker";
  isRtl: boolean;
  themeSettings: Record<string, string>;
  appConfig: {
    clearSession: 0 | 1;
    allowSwitchToAda: 0 | 1;
    predefined?: {
      locationId?: string | number;
      categoryId?: string | number;
      serviceId?: string | number;
      providerId?: string | number;
      client?: {
        name?: string;
        email?: string;
        phone?: string;
      };
      fields?: Record<string, string | number | null>;
    };
  };
}
```

## Verification status

Captured directly from the live SimplyBook demo iframe designer with Playwright on 15 July 2026.
