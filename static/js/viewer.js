const params = new URLSearchParams(location.search);
const name = params.get('s');
const token = params.get('t');

if (name && token) {
  // Pass token as arg for basic auth with ttyd
  document.getElementById('term').src = `${window.BASE_PATH}/tty/${name}/?arg=sangcode:${token}`;
  document.getElementById('session-title').textContent = name;
}

document.getElementById('kill-btn').onclick = async () => {
    if(!confirm('Kill session?')) return;
    await fetch(`${window.BASE_PATH}/api/sessions/${name}`, {method: 'DELETE'});
    location.href = `${window.BASE_PATH}/`;
};
