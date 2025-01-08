window.addEventListener('load', function(){
  $(document).ready(function() {

    // Code example switching
    let codeExampleControl = $('#api-access-example-code-control');
    let codeBlocks = $('#api-access-accordion').find('figure');

    if( codeExampleControl.length > 0 ){

      let controlButtons = $(codeExampleControl).find('input[name="api-access-example-code"]');

      if( controlButtons.length > 0 ){

        $(controlButtons).on('change', function(_event){

          let selectedCode = $(codeExampleControl).find('input[name="api-access-example-code"]:checked').val();

          $(codeBlocks).each(function(_index, _codeBlock){

            if( $(_codeBlock).hasClass(selectedCode) ){

              $(_codeBlock).show();

            }else{

              $(_codeBlock).hide();

            }

          });

        });

      }

    }

    // Activity tab link
    let activityTab = $('#activity-lnk');

    if( activityTab.length > 0 ){

      let link = $('#activity').find('a').first().attr('href');

      if( link && link.length > 0 ){

        $(activityTab).attr('href', link);
        $(activityTab).removeAttr('aria-controls');
        $(activityTab).attr('tabindex', 0);

        $(activityTab).off('click');
        $(activityTab).off('keyup');

        function _goto_activity(){
          window.location = link;
        }

        $(activityTab).on('click.Link', function(_event){
          _event.preventDefault();
          _goto_activity();
        });
        $(activityTab).on('keyup.Link', function(_event){
          let keyCode = _event.keyCode ? _event.keyCode : _event.which;
          // space and enter keys required for a11y
          if( keyCode == 32 || keyCode == 13 ){
            _event.preventDefault();
            _goto_activity();
          }
        });

      }

    }

  });
});
