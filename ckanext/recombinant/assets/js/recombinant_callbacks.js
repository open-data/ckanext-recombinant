window.addEventListener('load', function(){
  $(document).ready(function(){

    let uploadField = $('.recombinant-upload-field');
    if( uploadField.length > 0 ){
      $(uploadField).each(function(_index, _uploadField){
        // FIXME: not binding to node...
        $(_uploadField).on('invalid', function(_event){
          _uploadField[0].setCustomValidity($(_uploadField).attr('data-invalid-text'));
        });
        $(_uploadField).on('change', function(_event){
          console.log($(_uploadField).attr('data-invalid-text'));
          _uploadField[0].setCustomValidity('');
        });
      });
    }

    let deleteField = $('.recombinant-delete-field');
    if( deleteField.length > 0 ){
      $(deleteField).each(function(_index, _deleteField){
        $(_deleteField).on('invalid', function(_event){
          _deleteField[0].setCustomValidity($(_deleteField).attr('data-invalid-text'));
        });
        $(_deleteField).on('change', function(_event){
          _deleteField[0].setCustomValidity('');
        });
      });
    }

    let orgSelect = $('.recombinant-org-field');
    if( orgSelect.length > 0 ){
      $(orgSelect).on('change', function(_event){
        window.location.href = this.value;
      });
    }

  });
});