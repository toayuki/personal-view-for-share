const result = document.getElementById("result");
const contentsType = result?.dataset.contentsType;

fetch(`http://192.168.0.7:8000/${contentsType}/getList`)
  .then(response => response.json())
  .then(data => {
    data.items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "grid-item js-anim-item";
      li.dataset.id = item.id;

      const linkArea = document.createElement("div");
      linkArea.className = "options-area";

      const editLink = document.createElement("a");
      editLink.href = "#";
      editLink.classList.add("edit-link");
      editLink.textContent = "edit";
      editLink.dataset.id = item.id;
      editLink.dataset.title = item.title ?? "";
      linkArea.appendChild(editLink);

      const link = document.createElement("a");
      link.href = "#";
      link.classList.add("delete-link");
      link.textContent = "delete";
      link.dataset.id = item.id;
      linkArea.appendChild(link);

      const forceDeleteLink = document.createElement("a");
      forceDeleteLink.href = "#";
      forceDeleteLink.classList.add("force-delete-link");
      forceDeleteLink.textContent = "force";
      forceDeleteLink.dataset.id = item.id;
      linkArea.appendChild(forceDeleteLink);

      li.appendChild(linkArea);

      const a = document.createElement("a");
      a.href = `http://192.168.0.7:3000/personal-web/contents/${contentsType}/${item.file_type === "video" ? "video" : "img"}/${item.file_name}`;
      a.dataset.fancybox = "gallery";
      a.dataset.type = item.file_type === "video" ? "html5video" : "image";

      const img = document.createElement("img");
      img.src = `http://192.168.0.7:3000/personal-web/contents/${contentsType}/thumbnail/${item.thumbnail_file_name ?? item.file_name}`;
      a.appendChild(img);

      li.appendChild(a);

      // 動画アイテムに変換中プログレスバーを追加（初期状態は converting クラスあり）
      if (item.file_type === "video" && item.stored_file_name) {
        li.dataset.storedFileName = item.stored_file_name;
        li.classList.add("converting");

        const overlay = document.createElement("div");
        overlay.className = "converting-overlay";

        const wrap = document.createElement("div");
        wrap.className = "converting-progress-wrap";
        const bar = document.createElement("div");
        bar.className = "converting-progress-bar";
        wrap.appendChild(bar);

        const label = document.createElement("span");
        label.textContent = "変換中 0%";

        overlay.appendChild(wrap);
        overlay.appendChild(label);
        li.appendChild(overlay);
      }

      result.appendChild(li);
    });

    // 全動画を1リクエストで一括チェックし、完了済みはすぐにオーバーレイを外す
    const videoItems = [...result.querySelectorAll(".grid-item.converting[data-stored-file-name]")];
    if (videoItems.length > 0) {
      fetchConversionStatuses(videoItems.map(el => el.dataset.storedFileName))
        .then(statuses => {
          videoItems.forEach(el => {
            const d = statuses[el.dataset.storedFileName];
            if (!d || d.status !== "converting") {
              el.classList.remove("converting");
            } else {
              _updateBar(el, d.progress ?? 0);
            }
          });
        })
        .catch(() => {});
    }

    startConversionPolling();
  })
  .catch(err => {
    if (result) result.textContent = "取得失敗";
    console.error(err);
  });

function _updateBar(item, progress) {
  const bar = item.querySelector(".converting-progress-bar");
  const label = item.querySelector(".converting-overlay span");
  if (bar) bar.style.width = `${progress}%`;
  if (label) label.textContent = `変換中 ${progress}%`;
}

function fetchConversionStatuses(names) {
  const params = new URLSearchParams(names.map(n => ["names", n]));
  return fetch(`/conversion-status?${params}`).then(r => r.json());
}

function startConversionPolling() {
  const interval = setInterval(async () => {
    const items = [...(result?.querySelectorAll(".grid-item.converting[data-stored-file-name]") ?? [])];
    if (items.length === 0) {
      clearInterval(interval);
      return;
    }
    try {
      const statuses = await fetchConversionStatuses(items.map(el => el.dataset.storedFileName));
      items.forEach(item => {
        const d = statuses[item.dataset.storedFileName];
        if (!d) return;
        _updateBar(item, d.progress ?? 0);
        if (d.status === "done" || d.status === "error") {
          item.classList.remove("converting");
        }
      });
    } catch {}
  }, 1000);
}
