const DEFAULT_STOP = "Głowackiego";
const STOP_STORAGE_KEY = "selectedStop";

function getSelectedStop() {
  return new URLSearchParams(location.search).get("stop")
    || localStorage.getItem(STOP_STORAGE_KEY)
    || DEFAULT_STOP;
}

function setSelectedStop(name) {
  localStorage.setItem(STOP_STORAGE_KEY, name);
  const url = new URL(location.href);
  url.searchParams.set("stop", name);
  history.replaceState(null, "", url);
}

function initStopPicker(onChange) {
  const input = document.getElementById("stop-input");
  const list = document.getElementById("stop-suggestions");
  input.value = getSelectedStop();
  setSelectedStop(input.value);

  let debounce;
  let requestSeq = 0;
  let active = -1;

  const options = () => Array.from(list.querySelectorAll("li[role=option]"));

  function close() {
    list.hidden = true;
    active = -1;
  }

  function choose(name) {
    input.value = name;
    close();
    setSelectedStop(name);
    onChange(name);
  }

  function highlight(index) {
    options().forEach((li, i) => li.classList.toggle("active", i === index));
    active = index;
  }

  function showResults(names) {
    if (names.length === 0) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "Brak wyników";
      list.replaceChildren(li);
    } else {
      list.replaceChildren(...names.map((name) => {
        const li = document.createElement("li");
        li.textContent = name;
        li.setAttribute("role", "option");
        // mousedown fires before the input's blur closes the list
        li.addEventListener("mousedown", (e) => {
          e.preventDefault();
          choose(name);
        });
        return li;
      }));
    }
    active = -1;
    list.hidden = false;
  }

  async function search() {
    const q = input.value.trim();
    if (!q) return close();
    const seq = ++requestSeq;
    try {
      const res = await fetch(`/api/stops?q=${encodeURIComponent(q)}`);
      if (!res.ok || seq !== requestSeq) return;
      showResults(await res.json());
    } catch { /* suggestions are best-effort */ }
  }

  input.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(search, 150);
  });

  input.addEventListener("focus", () => {
    input.select();
    if (input.value.trim()) search();
  });

  input.addEventListener("blur", close);

  input.addEventListener("keydown", (e) => {
    const opts = options();
    if (e.key === "ArrowDown" && opts.length) {
      e.preventDefault();
      highlight((active + 1) % opts.length);
    } else if (e.key === "ArrowUp" && opts.length) {
      e.preventDefault();
      highlight((active - 1 + opts.length) % opts.length);
    } else if (e.key === "Enter") {
      const pick = opts[active] || (opts.length === 1 ? opts[0] : null);
      if (pick) choose(pick.textContent);
    } else if (e.key === "Escape") {
      close();
    }
  });
}
