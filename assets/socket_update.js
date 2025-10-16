// assets/socket_update.js
document.addEventListener("DOMContentLoaded", function() {
  var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
  socket.on('update_element', function (data) {
    const element = document.getElementById(data.target_id);
    if (element) {
      element.textContent = data.content;
    }
  });
});