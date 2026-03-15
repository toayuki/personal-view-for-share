fetch("http://192.168.0.7:8000/shiro/getList")
  .then(response => response.json())
  .then(data => {
    const result = document.getElementById("result");
    console.log("xxx結果", result)
    data.items.forEach((item, index) => {
      console.log("xxxxx", index)
      const li = document.createElement("li");
      li.className = "grid-item js-anim-item"

      // ===== 上に載せる delete 用 =====
      const overlay = document.createElement("div")
      overlay.className = "overlay"

      const linkArea = document.createElement("div")
      const link = document.createElement("a")
      link.href = `#`
      link.classList.add("delete-link")
      link.textContent = "delete"
      link.style.color = "white"
      link.dataset.id = item.id
      link.dataset.fancybox = index;
      linkArea.appendChild(link)
      // link.classList.add("overlay-link")
      li.appendChild(linkArea);

      const a = document.createElement("a");
      console.log("xxxxGetList実行")
      a.href = `http://192.168.0.7:3000/personal-web/contents/shiro/${item.file_type === "video" ? "video" : "img"}/${item.file_name}`
      a.dataset.fancybox = index;
      const img = document.createElement("img");
      img.src = `http://192.168.0.7:3000/personal-web/contents/shiro/thumbnail/${item.thumbnail_file_name ?? item.file_name}`;

      a.appendChild(img);

      li.appendChild(a);
      result.appendChild(li);
    });
    Fancybox.bind('[data-fancybox]', {
      Carousel: {
        preload: "none"  // 前後1枚だけ
      },
      Html: {
        video: {
          preload: "none"
        }
      }
    });
  })
  .catch(err => {
    console.log("xxxここ")
    document.getElementById("result").textContent = "取得失敗";
    console.error(err);
  });