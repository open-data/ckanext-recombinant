window.addEventListener('load', function(){
  $(document).ready(function(){

    function _bind_recombinant_validity(){
      let uploadField = $('.recombinant-upload-field');
      if( uploadField.length > 0 ){
        $(uploadField).each(function(_index, _uploadField){
          $(_uploadField).off('invalid.CustomMessage');
          $(_uploadField).on('invalid.CustomMessage', function(_event){
            $(_uploadField)[0].setCustomValidity($(_uploadField).attr('data-invalid-text'));
          });
          $(_uploadField).on('change', function(_event){
            $(_uploadField)[0].setCustomValidity('');
          });
        });
      }

      let deleteField = $('.recombinant-delete-field');
      if( deleteField.length > 0 ){
        $(deleteField).each(function(_index, _deleteField){
          $(_deleteField).off('invalid.CustomMessage');
          $(_deleteField).on('invalid.CustomMessage', function(_event){
            $(_deleteField)[0].setCustomValidity($(_deleteField).attr('data-invalid-text'));
          });
          $(_deleteField).on('change', function(_event){
            $(_deleteField)[0].setCustomValidity('');
          });
        });
      }
    }

    // NOTE: wet-boew tabs repaints contents of tab bodies, have to wait a bit...
    setTimeout(_bind_recombinant_validity, 750);

    let orgSelect = $('.recombinant-org-field');
    if( orgSelect.length > 0 ){
      $(orgSelect).on('change', function(_event){
        window.location.href = this.value;
      });
    }

  });
});