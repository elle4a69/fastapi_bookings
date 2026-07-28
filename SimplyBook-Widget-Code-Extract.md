# SimplyBook Widget Codes

## Booking Widget 1

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/react-widget/public/runtime.js"></script>
<script src="//widget.simplybook.net/react-widget/public/app.js"></script>
<link rel="stylesheet" href="//widget.simplybook.net/react-widget/public/app.css">

<div id="sb_widget"></div>

<script>
    window.addEventListener("load", () => {
        const themeSettings = {"colors_accent":"#183046","colors_accent_contrast":"#ffffff","colors_text":"#0b3052","colors_text_secondary":"#6d7785","colors_border":"#e7eaee","colors_background":"#ffffff","colors_link":"#216fec","font_sizes_h2":"24px","font_sizes_h3":"20px","font_sizes_p":"16px"};
        // const predefined = [];

        const widgetContainer = document.getElementById('sb_widget');
        SimplyBookWidget(widgetContainer, {
            apiKey: "e78a9bc986f7c1216b47ac6fdd568c106b9e4f3004013c8fdfb2df6a67927f1f",
            company: "bookings4me",
            baseUrl: "https://user-api-v2.simplybook.net",
            theme:  themeSettings
        });
    });
</script>
```

## Booking Widget 2

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/react-widget/public/runtime.js"></script>
<script src="//widget.simplybook.net/react-widget/public/app.js"></script>
<link rel="stylesheet" href="//widget.simplybook.net/react-widget/public/app.css">

<div id="sb_widget"></div>

<script>
    window.addEventListener("load", () => {
        const themeSettings = {"colors_accent":"#183046","colors_accent_contrast":"#ffffff","colors_text":"#0b3052","colors_text_secondary":"#6d7785","colors_border":"#e7eaee","colors_background":"#ffffff","colors_link":"#216fec","font_sizes_h2":"24px","font_sizes_h3":"20px","font_sizes_p":"16px"};
        // const predefined = [];

        const widgetContainer = document.getElementById('sb_widget');
        SimplyBookWidget(widgetContainer, {
            apiKey: "e78a9bc986f7c1216b47ac6fdd568c106b9e4f3004013c8fdfb2df6a67927f1f",
            company: "bookings4me",
            baseUrl: "https://user-api-v2.simplybook.net",
            theme:  themeSettings
        });
    });
</script>
```

## Reviews Widget 1

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"reviews","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"0","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":null,"datepicker":null,"is_rtl":false,"app_config":{"predefined":[]},"reviews_count":"0","hide_add_reviews":0});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_1zbhpl"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"reviews","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"0","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":null,"datepicker":null,"is_rtl":false,"app_config":{"predefined":[]},"reviews_count":"0","hide_add_reviews":0,"container_id":"sbw_1zbhpl"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_1zbhpl');
</script>
```

## Reviews Widget 2

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"reviews","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"0","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":null,"datepicker":null,"is_rtl":false,"app_config":{"predefined":[]},"reviews_count":"0","hide_add_reviews":0});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_1zbhpl"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"reviews","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"0","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":null,"datepicker":null,"is_rtl":false,"app_config":{"predefined":[]},"reviews_count":"0","hide_add_reviews":0,"container_id":"sbw_1zbhpl"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_1zbhpl');
</script>
```

## Reviews Widget 3

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"reviews","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"0","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":null,"datepicker":null,"is_rtl":false,"app_config":{"predefined":[]},"reviews_count":"0","hide_add_reviews":0});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_1zbhpl"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"reviews","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"0","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":null,"datepicker":null,"is_rtl":false,"app_config":{"predefined":[]},"reviews_count":"0","hide_add_reviews":0,"container_id":"sbw_1zbhpl"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_1zbhpl');
</script>
```

## Button Widget 1

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"button","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":"classes_plugin","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":[]},"button_title":"Book now","button_background_color":"#f72585","button_text_color":"#ffffff","button_position":"right","button_position_offset":"55%"});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_1zmxxj"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"button","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":"classes_plugin","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":[]},"button_title":"Book now","button_background_color":"#f72585","button_text_color":"#ffffff","button_position":"right","button_position_offset":"55%","container_id":"sbw_1zmxxj"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_1zmxxj');
</script>
```

## Button Widget 2

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"button","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":"classes_plugin","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":[]},"button_title":"Book now","button_background_color":"#f72585","button_text_color":"#ffffff","button_position":"right","button_position_offset":"55%"});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_1zmxxj"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"button","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":"classes_plugin","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":[]},"button_title":"Book now","button_background_color":"#f72585","button_text_color":"#ffffff","button_position":"right","button_position_offset":"55%","container_id":"sbw_1zmxxj"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_1zmxxj');
</script>
```

## Button Widget 3

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"button","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":"classes_plugin","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":[]},"button_title":"Book now","button_background_color":"#f72585","button_text_color":"#ffffff","button_position":"right","button_position_offset":"55%"});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_1zmxxj"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"button","url":"https:\/\/bookings4me.simplybook.net","theme":"emeri","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#836055","display_item_mode":"block","booking_nav_bg_color":"#ffffff","body_bg_color":"#f7f7f7","sb_review_image":"","dark_font_color":"#443936","light_font_color":"#ffffff","btn_color_1":"#a1776a","sb_company_label_color":"#896d65","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#e2eaec"},"timeline":"classes_plugin","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":[]},"button_title":"Book now","button_background_color":"#f72585","button_text_color":"#ffffff","button_position":"right","button_position_offset":"55%","container_id":"sbw_1zmxxj"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_1zmxxj');
</script>
```

## Iframe Widget 1

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"iframe","url":"https:\/\/bookings4me.simplybook.net","theme":"blur","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#cf1259","display_item_mode":"block","body_bg_color":"#f2f2f2","dark_font_color":"#474747","light_font_color":"#ffffff","btn_color_1":"#bd0b5c","sb_company_label_color":"#cd0c64","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#d6ebff"},"timeline":"modern","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":{"location":"1","category":"1"}}});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_mtpvrl"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"iframe","url":"https:\/\/bookings4me.simplybook.net","theme":"blur","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#cf1259","display_item_mode":"block","body_bg_color":"#f2f2f2","dark_font_color":"#474747","light_font_color":"#ffffff","btn_color_1":"#bd0b5c","sb_company_label_color":"#cd0c64","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#d6ebff"},"timeline":"modern","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":{"location":"1","category":"1"}},"container_id":"sbw_mtpvrl"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_mtpvrl');
</script>
```

## Iframe Widget 2

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"iframe","url":"https:\/\/bookings4me.simplybook.net","theme":"blur","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#cf1259","display_item_mode":"block","body_bg_color":"#f2f2f2","dark_font_color":"#474747","light_font_color":"#ffffff","btn_color_1":"#bd0b5c","sb_company_label_color":"#cd0c64","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#d6ebff"},"timeline":"modern","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":{"location":"1","category":"1"}}});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_mtpvrl"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"iframe","url":"https:\/\/bookings4me.simplybook.net","theme":"blur","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#cf1259","display_item_mode":"block","body_bg_color":"#f2f2f2","dark_font_color":"#474747","light_font_color":"#ffffff","btn_color_1":"#bd0b5c","sb_company_label_color":"#cd0c64","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#d6ebff"},"timeline":"modern","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":{"location":"1","category":"1"}},"container_id":"sbw_mtpvrl"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_mtpvrl');
</script>
```

## Iframe Widget 3

### Add code to webpage to offer booking option on your existing site

```html
<script src="//widget.simplybook.net/v2/widget/widget.js" type="text/javascript"></script>
<script type="text/javascript">
    var widget = new SimplybookWidget({"widget_type":"iframe","url":"https:\/\/bookings4me.simplybook.net","theme":"blur","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#cf1259","display_item_mode":"block","body_bg_color":"#f2f2f2","dark_font_color":"#474747","light_font_color":"#ffffff","btn_color_1":"#bd0b5c","sb_company_label_color":"#cd0c64","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#d6ebff"},"timeline":"modern","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":{"location":"1","category":"1"}}});
</script>
```

### Add the HTML container in the required place on your site

```html
<div id="sbw_mtpvrl"></div>
```

### Add JS code anywhere on your site

```html
<script type="text/javascript">
    (function(w, d, s, i) {
        var script = d.createElement(s);
        script.async = true;
        script.src = "//widget.simplybook.net/v2/widget/widget.js";
        script.onload = function() {
            new SimplybookWidget({"widget_type":"iframe","url":"https:\/\/bookings4me.simplybook.net","theme":"blur","theme_settings":{"timeline_hide_unavailable":"1","hide_past_days":"0","timeline_show_end_time":"0","timeline_modern_display":"as_slots","sb_base_color":"#cf1259","display_item_mode":"block","body_bg_color":"#f2f2f2","dark_font_color":"#474747","light_font_color":"#ffffff","btn_color_1":"#bd0b5c","sb_company_label_color":"#cd0c64","hide_img_mode":"0","sb_busy":"#c7b3b3","sb_available":"#d6ebff"},"timeline":"modern","datepicker":"top_calendar","is_rtl":false,"app_config":{"clear_session":0,"allow_switch_to_ada":0,"predefined":{"location":"1","category":"1"}},"container_id":"sbw_mtpvrl"});
        };
        d.head.appendChild(script);
    })(window, document, 'script', 'sbw_mtpvrl');
</script>
```
