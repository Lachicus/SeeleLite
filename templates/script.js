
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('service-worker.js')
        .then((registration) => {
          console.log('Service Worker registered with scope:', registration.scope);
        })
        .catch((error) => {
          console.error('Service Worker registration failed:', error);
        });
    });
}

let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  showInstallButton();
});

// Function to show your custom install button
function showInstallButton() {
  const installButton = document.getElementById('install-button');

  if (installButton) {
    installButton.style.display = 'block';

    installButton.addEventListener('click', () => {
      // Trigger the installation prompt
      deferredPrompt.prompt();

      // Wait for the user to respond to the prompt
      deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
          console.log('User accepted the installation');
        } else {
          console.log('User dismissed the installation');
        }

        // Reset the deferred prompt
        deferredPrompt = null;
        installButton.style.display = 'none';
      });
    });
  }
}

const statusIndicator = document.querySelector('.status-indicator');
const statusText = statusIndicator.nextElementSibling;

function checkConnection() {
    fetch("/ping", { cache: "no-cache" })
      .then((response) => {
        if (response.ok) {
          statusIndicator.style.backgroundColor = "#10b981"; // green
          statusText.textContent = "Online";
        } else {
          setOffline();
        }
      })
      .catch((error) => {
        setOffline();
      });
  }

function setOffline() {
    statusIndicator.style.backgroundColor = "#ef4444"; // red
    statusText.textContent = "Offline";
}

  // Run initially, then every 30 seconds
checkConnection();
setInterval(checkConnection, 30000);


async function checkSeeleStatus() {
    try {
      const res = await fetch('/ping');
      if (res.ok) {
        document.getElementById('access-message').style.display = 'block';
      } else {
        document.getElementById('access-message').style.display = 'none';
      }
    } catch (err) {
      document.getElementById('access-message').style.display = 'none';
    }
  }

checkSeeleStatus();
setInterval(checkSeeleStatus, 15000); // 15 seconds