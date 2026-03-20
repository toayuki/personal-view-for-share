import { onOpenConfirm } from "./modal.js";
import { onOpenEdit } from "./editModal.js";

//Gメニュー
var bnrBtn = $('#g_navi');
var $header = $('header');
var scrollpos;

$('.bg_bl').hide();

var ttt = false;

$(function () {
  $(".menu_btn").on("click", function () {
    if (ttt == false) {
      bnrBtn.stop().fadeIn();
      $('.bg_bl').fadeIn();
      scrollpos = $(window).scrollTop();
      $(".menu_btn").addClass('opened');
      ttt = true;
    } else {
      bnrBtn.stop().fadeOut();
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

document.getElementById('fileUpload')?.addEventListener('change', async (e) => {
  const files = Array.from(e.target.files ?? []);
  if (files.length === 0) return;

  spinner.classList.remove('loaded');

  for (const file of files) {
    await new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);

      const xhr = new XMLHttpRequest();

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          console.log(`アップロード中 [${file.name}]: ${percent}%`);
        }
      };

      xhr.onload = () => {
        console.log(`アップロード成功: ${file.name}`);
        resolve();
      };

      xhr.onerror = () => {
        console.error(`アップロード失敗: ${file.name}`);
        reject();
      };

      const contentsType = document.getElementById('result')?.dataset.contentsType ?? 'shiro';
      xhr.open('POST', `/upload/${contentsType}`);
      xhr.send(formData);
    }).catch(() => {});
  }

  spinner.classList.add('loaded');
  location.reload();
});

const optionsBtn = document.getElementById("optionsBtn");

function getSelectedItems() {
  return Array.from(document.querySelectorAll(".grid-item.selected"));
}

if (optionsBtn) {
  optionsBtn.addEventListener("click", () => {
    const isEditMode = document.body.classList.toggle("edit-mode");
    optionsBtn.textContent = isEditMode ? "done" : "options";
    if (!isEditMode) {
      document.querySelectorAll(".grid-item.selected").forEach(el => el.classList.remove("selected"));
    }
  });
}

const selectAllBtn = document.getElementById("selectAllBtn");
if (selectAllBtn) {
  selectAllBtn.addEventListener("click", () => {
    const allItems = document.querySelectorAll(".grid-item");
    const allSelected = [...allItems].every(el => el.classList.contains("selected"));
    allItems.forEach(el => el.classList.toggle("selected", !allSelected));
  });
}

document.addEventListener("click", async (e) => {
  if (document.body.classList.contains("edit-mode")) {
    const thumbnail = e.target.closest(".grid-item a[data-fancybox]");
    if (thumbnail) {
      e.preventDefault();
      thumbnail.closest(".grid-item").classList.toggle("selected");
      return;
    }
  }

  const deleteLink = e.target.closest(".delete-link");
  if (deleteLink) {
    e.preventDefault();
    const isEditMode = document.body.classList.contains("edit-mode");
    const selectedItems = getSelectedItems();
    if (isEditMode && selectedItems.length > 0) {
      const clickedItem = deleteLink.closest(".grid-item");
      if (clickedItem && !clickedItem.classList.contains("selected")) {
        clickedItem.classList.add("selected");
      }
      const targets = getSelectedItems();
      await onOpenConfirm({
        message: `${targets.length}件を削除しますか？`,
        onOk: async () => {
          for (const item of targets) {
            try {
              const res = await fetch(`/delete/${item.dataset.id}`);
              if (!res.ok) throw new Error(`delete failed: ${res.status}`);
              item.remove();
            } catch (err) {
              console.error("削除に失敗しました", err);
            }
          }
        },
      });
    } else {
      const targetId = deleteLink.dataset.id;
      await onOpenConfirm({
        message: "本当に削除しますか？",
        onOk: async () => {
          try {
            const res = await fetch(`/delete/${targetId}`);
            if (!res.ok) throw new Error(`delete failed: ${res.status}`);
            deleteLink.closest(".grid-item")?.remove();
          } catch (err) {
            console.error("削除に失敗しました", err);
          }
        }
      });
    }
  }

  const forceDeleteLink = e.target.closest(".force-delete-link");
  if (forceDeleteLink) {
    e.preventDefault();
    const isEditMode = document.body.classList.contains("edit-mode");
    const selectedItems = getSelectedItems();
    if (isEditMode && selectedItems.length > 0) {
      const clickedItem = forceDeleteLink.closest(".grid-item");
      if (clickedItem && !clickedItem.classList.contains("selected")) {
        clickedItem.classList.add("selected");
      }
      const targets = getSelectedItems();
      await onOpenConfirm({
        message: `ファイルを含む全データ ${targets.length}件を削除します。元に戻せません。`,
        onOk: async () => {
          for (const item of targets) {
            try {
              const res = await fetch(`/forceDelete/${item.dataset.id}`);
              if (!res.ok) throw new Error(`force delete failed: ${res.status}`);
              item.remove();
            } catch (err) {
              console.error("強制削除に失敗しました", err);
            }
          }
        },
      });
    } else {
      const targetId = forceDeleteLink.dataset.id;
      await onOpenConfirm({
        message: "ファイルを含む全データを削除します。元に戻せません。",
        onOk: async () => {
          try {
            const res = await fetch(`/forceDelete/${targetId}`);
            if (!res.ok) throw new Error(`force delete failed: ${res.status}`);
            forceDeleteLink.closest(".grid-item")?.remove();
          } catch (err) {
            console.error("強制削除に失敗しました", err);
          }
        },
      });
    }
  }

  const editLink = e.target.closest(".edit-link");
  if (editLink) {
    e.preventDefault();
    await onOpenEdit({
      id: editLink.dataset.id,
      title: editLink.dataset.title,
      onSave: async ({ title }) => {
        try {
          const res = await fetch(`http://192.168.0.7:8000/update/${editLink.dataset.id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
          });
          if (!res.ok) throw new Error(`update failed: ${res.status}`);
          editLink.dataset.title = title;
        } catch (err) {
          console.error("更新に失敗しました", err);
        }
      },
    });
  }
})
