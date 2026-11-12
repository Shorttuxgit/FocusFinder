let port = browser.runtime.connectNative("browser");
let username = "";
let password = "";
let do_upass = false;
port.onMessage.addListener(response => {

    username = response.username;
    password = response.password;
    do_upass = true;
});

function on_login()
{
    console.log(`MESSAGE2 ${details.url} url pass ${password}`);
}

function on_url(details)
{
    console.log("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    if(details.url == "https://focus.barton.ac.uk/login" && do_upass)
    {
        console.log("href...");
        browser.tabs.executeScript(details.tabId, {code: "document.getElementsByClassName(\"group relative flex w-full items-center justify-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm font-medium text-gray-700 shadow-xs transition-all duration-200 hover:border-gray-300 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2\")[0].click()"});
    }
    if(details.url.includes("confirmidentifier") && do_upass)
    {
        console.log("href2...");
        browser.tabs.executeScript(details.tabId, {code: "let buttons = document.querySelectorAll(\"button[type='button']\"); for(let i = 0; i < buttons.length; i++) { let button = buttons[i]; if(button.textContent.trim() == 'Next') button.click(); } function mf() { if (document.querySelector(\"input[type='password']\") && document.querySelector(\"input[type='password']\") == document.activeElement) { console.log(\"got passwd\"); document.querySelector(\"input[type='password']\").value += \"" + password + "\"; let buttons = document.querySelectorAll(\"button[type='button']\"); for(let i = 0; i < buttons.length; i++) { let button = buttons[i]; if(button.textContent.trim() == 'Next') button.click(); } } else { setTimeout(mf, 1000); } }; mf();"});
    }
    else if(details.url.includes("identifier") && do_upass)
    {
        console.log("href3...");
        browser.tabs.executeScript(details.tabId, {code: "document.querySelector(\"input[type='text']\").value += \"" + username + "\"; let buttons = document.querySelectorAll(\"button[type='button']\"); for(let i = 0; i < buttons.length; i++) { let button = buttons[i]; if(button.textContent.trim() == 'Next') button.click(); } function mf() { if (document.querySelector(\"input[type='password']\") && document.querySelector(\"input[type='password']\") == document.activeElement) { console.log(\"got passwd\"); document.querySelector(\"input[type='password']\").value += \"" + password + "\"; let buttons = document.querySelectorAll(\"button[type='button']\"); for(let i = 0; i < buttons.length; i++) { let button = buttons[i]; if(button.textContent.trim() == 'Next') button.click(); } } else { setTimeout(mf, 1000); } }; mf();"})
    }
    if(details.url.includes("home") && details.url.includes("barton"))
    {
        let val = browser.tabs.executeScript(details.tabId, {code: "document.getElementsByClassName(\"text-3xl font-bold\")[0].textContent.trim();"});
        val.then((value) => {
            port.postMessage(`${value[0]}`);
        });
    }
    console.log(`MESSAGE ${details.url} url pass ${password}`);
}
console.log("INITIALISED");
browser.webNavigation.onCompleted.addListener(on_url, {
      url: [{ urlMatches: ".*" }],
});