import { onOpenConfirm } from "./modal.js";

//Gメニュー
var bnrBtn = $('#g_navi');
var menuOpen = false;
var $header = $('header');
var scrollpos;

$('.bg_bl').hide();

var ttt = false;

$(function () {
  $(".menu_btn").on("click", function () {
    if (ttt == false) {
      bnrBtn.stop().fadeIn();
      menuOpen = true;
      $('.bg_bl').fadeIn();
      scrollpos = $(window).scrollTop();
      $(".menu_btn").addClass('opened');
      ttt = true;
    } else {
      bnrBtn.stop().fadeOut();
      menuOpen = false;
      $('.bg_bl').fadeOut();
      $(".menu_btn").removeClass('opened');
      window.scrollTo(0, scrollpos);
      ttt = false;
    }
  });
});


$(window).scroll(function () {
  if ($(window).scrollTop() > 30) {
    $header.addClass('fixed');
  } else {
    $header.removeClass('fixed');
  }
});



// ローディング処理

window.onload = function () {
  const spinner = document.getElementById('loading');
  spinner.classList.add('loaded');
  $('.grid').toggleClass('animated');
  $('.grid-item').each(function (index) {
    var delay = 0.01 * index;
    $(this).css({
      'transition-delay': delay + 's'
    });
  });

}

const spinner = document.getElementById('loading');

// ファイルアップロード処理

document.getElementById('fileUpload').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  // アップロード開始 → ローディング表示
  spinner.classList.remove('loaded');

  const xhr = new XMLHttpRequest();

  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) {
      const percent = Math.round((event.loaded / event.total) * 100);
      console.log(`アップロード中: ${percent}%`);
    }
  }

  xhr.onload = () => {
    // ✅ 完了 → ローディング非表示
    spinner.classList.add('loaded');
    console.log('アップロード成功', xhr.responseText);
    location.reload()
  };

  xhr.onerror = () => {
    spinner.classList.add('loaded');
    console.error('アップロード失敗');
  };

  xhr.open('POST', '/upload/shiro');
  xhr.send(formData);
});

document.addEventListener("click", async (e) => {
  console.log("xxx呼ばれた")
  const deleteLink = e.target.closest(".delete-link");
  if (deleteLink) {
    e.preventDefault()
    const targetId = deleteLink.dataset.id;
    console.log("xxxxxここ")
    await onOpenConfirm({message: "本当に削除しますか？",onOk: async()=>{
      console.log("xxx削除実行")
    }})
        console.log("xxxxxここ2")
    // try {
    //   const res = await fetch(`/api/delete/${targetId}`, {
    //     method: "DELETE",
    //     headers: {
    //       "Content-Type": "application/json"
    //     }
    //   });

    //   if (!res.ok) {
    //     throw new Error(`delete failed: ${res.status}`);
    //   }

    //   // 削除成功 → リロード
    //   location.reload();

    // } catch (err) {
    //   alert("削除に失敗しました");
    //   console.error(err);
    // }
  }
})
