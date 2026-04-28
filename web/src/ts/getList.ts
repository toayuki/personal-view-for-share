export interface ContentItem {
  id: string;
  title?: string;
  file_name: string;
  file_type: 'image' | 'video';
  thumbnail_file_name?: string;
  stored_file_name?: string;
}

interface ConversionStatus {
  status: 'waiting' | 'converting' | 'done' | 'error';
  progress?: number;
}

const result = document.getElementById('result') as HTMLUListElement | null;
const categoryId = result?.dataset.categoryId;
const API_BASE = window.API_BASE;

if (result && categoryId) {
  fetch(`${API_BASE}/${categoryId}/getList`)
    .then(res => res.json())
    .then((data: { items: ContentItem[] }) => {
      data.items.forEach(item => result.appendChild(createGridItem(item)));

      // 全動画を一括チェックし、変換中のものだけオーバーレイを追加
      const videoItems = [...result.querySelectorAll<HTMLLIElement>('.grid-item[data-stored-file-name]')];
      if (videoItems.length > 0) {
        fetchConversionStatuses(videoItems.map(el => el.dataset.storedFileName!))
          .then(statuses => {
            videoItems.forEach(el => {
              const d = statuses[el.dataset.storedFileName!];
              if (d && d.status !== 'done' && d.status !== 'error') {
                addConvertingOverlay(el);
                _updateBar(el, d.progress ?? 0, d.status);
              }
            });
            startConversionPolling();
          })
          .catch(() => {});
      }
    })
    .catch(err => {
      if (result) result.textContent = '取得失敗';
      console.error(err);
    });
}

export function createGridItem(item: ContentItem): HTMLLIElement {
  const li = document.createElement('li');
  li.className = 'grid-item js-anim-item';
  li.dataset.id = item.id;

  const linkArea = document.createElement('div');
  linkArea.className = 'options-area';

  const editLink = document.createElement('a');
  editLink.href = '#';
  editLink.classList.add('edit-link');
  editLink.textContent = 'edit';
  editLink.dataset.id = item.id;
  editLink.dataset.title = item.title ?? '';
  linkArea.appendChild(editLink);

  const deleteLink = document.createElement('a');
  deleteLink.href = '#';
  deleteLink.classList.add('delete-link');
  deleteLink.textContent = 'delete';
  deleteLink.dataset.id = item.id;
  linkArea.appendChild(deleteLink);

  const forceDeleteLink = document.createElement('a');
  forceDeleteLink.href = '#';
  forceDeleteLink.classList.add('force-delete-link');
  forceDeleteLink.textContent = 'force';
  forceDeleteLink.dataset.id = item.id;
  linkArea.appendChild(forceDeleteLink);

  const downloadLink = document.createElement('a');
  downloadLink.href = `/download/${item.id}`;
  downloadLink.classList.add('download-link');
  downloadLink.textContent = 'download';
  downloadLink.dataset.id = item.id;
  linkArea.appendChild(downloadLink);

  li.appendChild(linkArea);

  const a = document.createElement('a');
  a.href = `/personal-web/contents/${categoryId}/${item.file_type === 'video' ? 'video' : 'img'}/${item.file_name}`;
  a.dataset.fancybox = 'gallery';
  a.dataset.type = item.file_type === 'video' ? 'html5video' : 'image';

  const img = document.createElement('img');
  img.src = `/personal-web/contents/${categoryId}/thumbnail/${item.thumbnail_file_name ?? item.file_name}`;
  a.appendChild(img);

  const typeIcon = document.createElement('span');
  typeIcon.className = 'file-type-icon';
  typeIcon.innerHTML = item.file_type === 'video'
    ? '<i class="fa-solid fa-film"></i> VIDEO'
    : '<i class="fa-regular fa-image"></i> PHOTO';
  a.appendChild(typeIcon);

  li.appendChild(a);
  li.appendChild(linkArea);

  if (item.file_type === 'video' && item.stored_file_name) {
    li.dataset.storedFileName = item.stored_file_name;
  }

  return li;
}

export function addConvertingOverlay(item: HTMLElement): void {
  if (item.classList.contains('converting')) return;
  item.classList.add('converting');
  const overlay = document.createElement('div');
  overlay.className = 'converting-overlay';
  const wrap = document.createElement('div');
  wrap.className = 'converting-progress-wrap';
  const bar = document.createElement('div');
  bar.className = 'converting-progress-bar';
  wrap.appendChild(bar);
  const label = document.createElement('span');
  label.textContent = '変換中 0%';
  overlay.appendChild(wrap);
  overlay.appendChild(label);
  item.appendChild(overlay);
}

function _updateBar(item: HTMLElement, progress: number, status: string): void {
  const bar = item.querySelector<HTMLElement>('.converting-progress-bar');
  const label = item.querySelector<HTMLElement>('.converting-overlay span');
  const isWaiting = status === 'waiting';
  if (bar) bar.style.width = isWaiting ? '0%' : `${progress}%`;
  if (label) label.textContent = isWaiting ? '待機中' : `変換中 ${progress}%`;
  if (label) label.dataset.status = status ?? 'converting';
}

function fetchConversionStatuses(names: string[]): Promise<Record<string, ConversionStatus>> {
  const params = new URLSearchParams(names.map(n => ['names', n] as [string, string]));
  return fetch(`/conversion-status?${params}`).then(r => r.json());
}

let _pollingActive = false;

export function startConversionPolling(): void {
  if (_pollingActive) return;
  _pollingActive = true;
  const interval = setInterval(async () => {
    const converting = [...(result?.querySelectorAll<HTMLLIElement>('.grid-item.converting[data-stored-file-name]') ?? [])];
    if (converting.length === 0) {
      clearInterval(interval);
      _pollingActive = false;
      return;
    }
    try {
      const statuses = await fetchConversionStatuses(converting.map(el => el.dataset.storedFileName!));
      converting.forEach(item => {
        const d = statuses[item.dataset.storedFileName!];
        if (!d) return;
        _updateBar(item, d.progress ?? 0, d.status);
        if (d.status === 'done' || d.status === 'error') {
          item.classList.remove('converting');
          item.querySelector('.converting-overlay')?.remove();
        }
      });
    } catch {}
  }, 1000);
}
