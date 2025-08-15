window.addEventListener('load', function(){
  $(document).ready(function(){

    let uploadField = $('.recombinant-upload-field');
    if( uploadField.length > 0 ){
      $(uploadField).on('invalid', function(_event){
        uploadField.setCustomValidity($(uploadField).attr('data-invalid-text'));
      });
      $(uploadField).on('change', function(_event){
        uploadField.setCustomValidity('');
      });
    }

    let deleteField = $('.recombinant-delete-field');
    if( deleteField.length > 0 ){
      $(deleteField).on('invalid', function(_event){
        deleteField.setCustomValidity($(deleteField).attr('data-invalid-text'));
      });
      $(deleteField).on('change', function(_event){
        deleteField.setCustomValidity('');
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