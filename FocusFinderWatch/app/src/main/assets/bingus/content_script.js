const port = browser.runtime.connectNative("browser");

function logURL(details) {
      console.log(`${details.url} url`);
      //port.postMessage(`url: ${details.url}`);
      //port.postMessage({body: `${details.url}`});
      if(!details.url.includes("livewire") || !details.url.includes("update"))
            return {};
      //port.postMessage("got livewire");
      console.log(`got livewire`);
      //port.postMessage({body: "got livewire"} );
      let filter = browser.webRequest.filterResponseData(details.requestId);
      let decoder = new TextDecoder("utf-8");
      let body_full = "";
      filter.ondata = event => {
            let str = decoder.decode(event.data, {stream: true});
            body_full += str;
            //console.log(`${str}`);
            //port.postMessage(`${str}`);
      }
      filter.onstop = event => {

            body_full += decoder.decode();

            port.postMessage(`${body_full}`);

            filter.disconnect();
      }
      return {};
}

browser.webRequest.onBeforeRequest.addListener(logURL, {
      urls: ["<all_urls>"],
}, ["blocking"]);