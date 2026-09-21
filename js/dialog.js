// Keep the Hub iframe alive while hidden so searches and downloads survive closing.
export function createHubDialog({ start, url, standaloneUrl, text }) {
    let loaded = false;
    let opening = null;
    let previousFocus = null;
    let revision = 0;
    const dialog = document.createElement("dialog");
    dialog.className = "comfy-model-hub";
    dialog.setAttribute("aria-label", text.title);
    const header = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = text.title;
    const maximize = document.createElement("button");
    maximize.type = "button";
    maximize.textContent = text.maximize;
    maximize.setAttribute("aria-pressed", "false");
    maximize.onclick = () => {
        const expanded = dialog.classList.toggle("comfy-model-hub-maximized");
        maximize.setAttribute("aria-pressed", String(expanded));
        maximize.textContent = expanded ? text.restore : text.maximize;
    };
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = text.close;
    close.onclick = () => dialog.close();
    const newTab = document.createElement("a");
    newTab.href = standaloneUrl();
    newTab.target = "_blank";
    newTab.rel = "noopener noreferrer";
    newTab.textContent = text.newTab;
    header.append(title, newTab, maximize, close);
    const status = document.createElement("div");
    status.className = "comfy-model-hub-status";
    status.setAttribute("role", "status");
    const message = document.createElement("p");
    const retry = document.createElement("button");
    retry.type = "button";
    retry.textContent = text.retry;
    retry.onclick = () => void open(true);
    status.append(message, retry);
    const frame = document.createElement("iframe");
    frame.title = text.title;
    frame.hidden = true;
    frame.setAttribute("referrerpolicy", "same-origin");
    // Hub's OAuth flow uses a popup; same-origin embedding preserves its cookies.
    dialog.append(header, status, frame);
    document.body.append(dialog);
    let timeout;

    function failed(error) {
        clearTimeout(timeout);
        loaded = false;
        status.hidden = false;
        frame.hidden = true;
        message.textContent = `${text.failed} ${error.message || error}`;
        retry.hidden = false;
    }

    frame.addEventListener("load", () => {
        if (!frame.hasAttribute("src")) return;
        clearTimeout(timeout);
        const doc = frame.contentDocument;
        if (!doc?.querySelector("#app")) {
            failed(new Error(text.unavailable));
            return;
        }
        loaded = true;
        status.hidden = true;
        frame.hidden = false;
        doc.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !event.defaultPrevented &&
                !doc.querySelector('md-dialog[open], dialog[open], [role="dialog"][aria-modal="true"]')) {
                event.preventDefault();
                dialog.close();
            }
        });
    });
    frame.addEventListener("error", () => failed(new Error(text.unavailable)));
    dialog.addEventListener("close", () => previousFocus?.focus?.());

    async function open(forceReload = false) {
        if (!dialog.open) {
            previousFocus = document.activeElement;
            dialog.showModal();
        }
        if (opening) return opening;
        opening = (async () => {
            if (!loaded || forceReload) {
                message.textContent = text.loading;
                retry.hidden = true;
                status.hidden = false;
                frame.hidden = true;
            }
            try {
                await start();
                if (!loaded || forceReload) {
                    const target = new URL(url(), window.location.href);
                    // Reassigning an identical hash URL only navigates within the document;
                    // retry must load a fresh document so its load event fires again.
                    if (frame.hasAttribute("src")) target.searchParams.set("_comfyui_hub_reload", String(++revision));
                    frame.src = target.href;
                    clearTimeout(timeout);
                    timeout = setTimeout(() => failed(new Error(text.unavailable)), 45000);
                }
            } catch (error) {
                failed(error);
            }
        })();
        try { await opening; } finally { opening = null; }
    }

    return { open };
}
