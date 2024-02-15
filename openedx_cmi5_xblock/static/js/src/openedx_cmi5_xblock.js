/* Javascript for CMI5XBlock. */
function CMI5XBlock(runtime, element) {

  $(function($) {
      /*
      Use `gettext` provided by django-statici18n for static translations

      var gettext = CMI5XBlocki18n.gettext;
      */

      /* Here's where you'd do things on page load. */

      $('ol a').click(function(event) {
          event.preventDefault();
          var href = $(this).attr('href');
          var launchMethod = $(this).data("launch-method");
          updateIframeSrc(href, launchMethod);

      });

      function updateIframeSrc(href, launchMethod) {
          // TODO: Uncomment the code below when we have figured out a workaround of limitations imposed by
          // browsers while loading iframe from different domain than host
          launchMethod = 'OwnWindow';
          if (launchMethod === 'AnyWindow') {
              $('.cmi5-embedded').attr('src', href);
          } else {
              window.open(href, '_blank');
          }
      }
  });
}