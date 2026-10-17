let manifest = document.querySelector("head > link[rel=manifest]");
browser.runtime.sendNativeMessage("browser", "WORKKK");
if (manifest) {
     fetch(manifest.href)
        .then(response => response.json())
        .then(json => {
             let message = {type: "WPAManifest", manifest: json};
             browser.runtime.sendNativeMessage("browser", message);
        });
}