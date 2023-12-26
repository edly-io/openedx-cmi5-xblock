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
          var liText = $(this).closest('li').text().trim();
          updateIframeSrc(href, liText);

      });

      function updateIframeSrc(href, liText) {
          if (liText.includes('AnyWindow')) {
              $('.cmi5-embedded').attr('src', href);
          } else if (liText.includes('OwnWindow')) {
              window.open(href, '_blank');
          }
      }
  });
}