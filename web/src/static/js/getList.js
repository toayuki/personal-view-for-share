fetch("http://192.168.0.7:8000/shiro/getList")
  .then(response => response.json())
  .then(data => {
    const result = document.getElementById("result");
    console.log("xxx結果", result)
    data.items.forEach((item, index) => {
      console.log("xxxxx", index)
      const li = document.createElement("li");
      li.className = "grid-item js-anim-item"
      li.dataset.id = item.id

      // ===== 上に載せる delete 用 =====
      const overlay = document.createElement("div")
      overlay.className = "overlay"

      const linkArea = document.createElement("div")
      linkArea.className = "options-area"


      const editLink = document.createElement("a")
      editLink.href = `#`
      editLink.classList.add("edit-link")
      editLink.textContent = "edit"
      editLink.dataset.id = item.id
      editLink.dataset.title = item.title ?? ""
      linkArea.appendChild(editLink)

      const link = document.createElement("a")
      link.href = `#`
      link.classList.add("delete-link")
      link.textContent = "delete"
      link.dataset.id = item.id
      linkArea.appendChild(link)

      const forceDeleteLink = document.createElement("a")
      forceDeleteLink.href = `#`
      forceDeleteLink.classList.add("force-delete-link")
      forceDeleteLink.textContent = "force"
      forceDeleteLink.dataset.id = item.id
      linkArea.appendChild(forceDeleteLink)

      li.appendChild(linkArea);

      const a = document.createElement("a");
      console.log("xxxxGetList実行")
      a.href = `http://192.168.0.7:3000/personal-web/contents/shiro/${item.file_type === "video" ? "video" : "img"}/${item.file_name}`
      a.dataset.fancybox = "gallery";
      a.dataset.type = item.file_type === "video" ? "html5video" : "image";
      const img = document.createElement("img");
      img.src = `http://192.168.0.7:3000/personal-web/contents/shiro/thumbnail/${item.thumbnail_file_name ?? item.file_name}`;

      a.appendChild(img);

      li.appendChild(a);
      result.appendChild(li);
    });
  })
  .catch(err => {
    console.log("xxxここ")
    document.getElementById("result").textContent = "取得失敗";
    console.error(err);
  });