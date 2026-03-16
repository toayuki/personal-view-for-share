var slideshowDuration = 1500;
var slideshow=$('.main-content .slideshow');

function slideshowSwitch(slideshow,index,auto){
  if(slideshow.data('wait')) return;

  var slides = slideshow.find('.slide');
  var pages = slideshow.find('.pagination');
  var activeSlide = slides.filter('.is-active');
  var activeSlideImage = activeSlide.find('.image-container');
  var newSlide = slides.eq(index);
  var newSlideImage = newSlide.find('.image-container');
  var newSlideContent = newSlide.find('.slide-content');
  var newSlideElements=newSlide.find('.caption > *');
  if(newSlide.is(activeSlide))return;

  newSlide.addClass('is-new');
  var timeout=slideshow.data('timeout');
  clearTimeout(timeout);
  slideshow.data('wait',true);
  var pages=slideshow.find('.pagination .item');
  pages.removeClass('is-active');
  pages.eq(index).addClass('is-active');
  var transition=slideshow.attr('data-transition');
  if(transition=='fade'){
    newSlide.css({
      display:'block',
      zIndex:2
    });
    newSlideImage.css({
      opacity:0
    });

    TweenMax.to(newSlideImage,1,{
      alpha:1,
      onComplete:function(){
        newSlide.addClass('is-active').removeClass('is-new');
        activeSlide.removeClass('is-active');
        newSlide.css({display:'',zIndex:''});
        newSlideImage.css({opacity:''});
        slideshow.find('.pagination').trigger('check');
        slideshow.data('wait',false);
        if(auto){
          timeout=setTimeout(function(){
            slideshowNext(slideshow,false,true);
          },slideshowDuration);
          slideshow.data('timeout',timeout);}}});
  } else {
    if(newSlide.index()>activeSlide.index()){
      var newSlideRight=0;
      var newSlideLeft='auto';
      var newSlideImageRight=-slideshow.width()/8;
      var newSlideImageLeft='auto';
      var newSlideImageToRight=0;
      var newSlideImageToLeft='auto';
      var newSlideContentLeft='auto';
      var newSlideContentRight=0;
      var activeSlideImageLeft=-slideshow.width()/4;
    } else {
      var newSlideRight='';
      var newSlideLeft=0;
      var newSlideImageRight='auto';
      var newSlideImageLeft=-slideshow.width()/8;
      var newSlideImageToRight='';
      var newSlideImageToLeft=0;
      var newSlideContentLeft=0;
      var newSlideContentRight='auto';
      var activeSlideImageLeft=slideshow.width()/4;
    }

    newSlide.css({
      display:'block',
      width:0,
      right:newSlideRight,
      left:newSlideLeft
      ,zIndex:2
    });

    newSlideImage.css({
      width:slideshow.width(),
      right:newSlideImageRight,
      left:newSlideImageLeft
    });

    newSlideContent.css({
      width:slideshow.width(),
      left:newSlideContentLeft,
      right:newSlideContentRight
    });

    activeSlideImage.css({
      left:0
    });

    TweenMax.set(newSlideElements,{y:20,force3D:true});
    TweenMax.to(activeSlideImage,1,{
      left:activeSlideImageLeft,
      ease:Power3.easeInOut
    });

    TweenMax.to(newSlide,1,{
      width:slideshow.width(),
      ease:Power3.easeInOut
    });

    TweenMax.to(newSlideImage,1,{
      right:newSlideImageToRight,
      left:newSlideImageToLeft,
      ease:Power3.easeInOut
    });

    TweenMax.staggerFromTo(newSlideElements,0.8,{alpha:0,y:60},{alpha:1,y:0,ease:Power3.easeOut,force3D:true,delay:0.6},0.1,function(){
      newSlide.addClass('is-active').removeClass('is-new');
      activeSlide.removeClass('is-active');
      newSlide.css({
        display:'',
        width:'',
        left:'',
        zIndex:''
      });

      newSlideImage.css({
        width:'',
        right:'',
        left:''
      });

      newSlideContent.css({
        width:'',
        left:''
      });

      newSlideElements.css({
        opacity:'',
        transform:''
      });

      activeSlideImage.css({
        left:''
      });

      slideshow.find('.pagination').trigger('check');
      slideshow.data('wait',false);
      if(auto){
        timeout=setTimeout(function(){
          slideshowNext(slideshow,false,true);
        },slideshowDuration);
        slideshow.data('timeout',timeout);
      }
    });
  }
}

function slideshowNext(slideshow,previous,auto){
  var slides=slideshow.find('.slide');
  var activeSlide=slides.filter('.is-active');
  var newSlide=null;
  if(previous){
    newSlide=activeSlide.prev('.slide');
    if(newSlide.length === 0) {
      newSlide=slides.last();
    }
  } else {
    newSlide=activeSlide.next('.slide');
    if(newSlide.length==0)
      newSlide=slides.filter('.slide').first();
  }

  slideshowSwitch(slideshow,newSlide.index(),auto);
}

function homeSlideshowParallax(){
  var scrollTop=$(window).scrollTop();
  if(scrollTop>windowHeight) return;
  var inner=slideshow.find('.slideshow-inner');
  var newHeight=windowHeight-(scrollTop/2);
  var newTop=scrollTop*0.8;

  inner.css({
    transform:'translateY('+newTop+'px)',height:newHeight
  });
}

function runIntroSequence(slideshow, onComplete) {
  var slides = slideshow.find('.slide');
  console.log("xxxx",slides)
  var pagination = slideshow.find('.pagination .item');
  var categorySlides = slides.filter(':not(.slide-add-category)');
  var categoryTotal = categorySlides.length;

  if (categoryTotal <= 1) { onComplete(); return; }

  var images = categorySlides.find('.image').toArray();
  var loadPromises = images.map(function(img) {
    return new Promise(function(resolve) {
      if (img.complete) { resolve(); return; }
      img.addEventListener('load', resolve);
      img.addEventListener('error', resolve);
    });
  });

  Promise.all(loadPromises).then(function() {
    var slidesContainer = slideshow.find('.slides');
    var w = slideshow.width();

    // 矢印・ページネーションを非表示
    slideshow.find('.arrows').css('visibility', 'hidden');
    slideshow.find('.pagination').css('visibility', 'hidden');

    // カテゴリスライドを横に並べる（slide-content は非表示）
    categorySlides.each(function(i) {
      $(this).css({ display: 'block', left: i * w, width: w, opacity: 1, zIndex: 2 });
      $(this).find('.slide-content').css('visibility', 'hidden');
      $(this).find('.image-container').css('width', w);
    });
    slidesContainer.css('width', categoryTotal * w);

    // 全スライドを右へ流す（カテゴリ数 × 0.4秒）
    TweenMax.to(slidesContainer, categoryTotal*0.4, {
      x: -(categoryTotal - 1) * w,
      ease: Power2.easeInOut,
      force3D: true,
      onComplete: function() {
        // ウェルカムテキストを生成
        var welcome = $('<div class="intro-welcome"><div class="intro-welcome-text">Share Your Memories</div></div>');
        slideshow.find('.slideshow-inner').append(welcome);
        var welcomeText = welcome.find('.intro-welcome-text');

        // 最初のスライドへ戻りながらテキストをフェードイン
        TweenMax.to(slidesContainer, 0.6, {
          x: 0,
          ease: Power2.easeOut,
          force3D: true,
        });
        TweenMax.to(welcomeText, 0.5, {
          opacity: 1,
          delay: 0.1,
          onComplete: function() {
            // テキストをフェードアウトしてリセット
            TweenMax.to(welcome, 0.5, {
              opacity: 0,
              ease: Power1.easeIn,
              delay: 0.8,
              onComplete: function() {
                welcome.remove();

                slideshow.find('.arrows').css('visibility', '');
                slideshow.find('.pagination').css('visibility', '');

                categorySlides.each(function() {
                  $(this).css({ display: '', left: '', width: '', opacity: '', zIndex: '' });
                  $(this).find('.slide-content').css('visibility', '');
                  $(this).find('.image-container').css('width', '');
                });
                TweenMax.set(slidesContainer, { clearProps: 'all' });
                slidesContainer.css('width', '');

                slides.removeClass('is-active');
                pagination.removeClass('is-active');
                slides.eq(0).addClass('is-active');
                pagination.eq(0).addClass('is-active');

                onComplete();
              }
            });
          }
        });
      }
    });
  });
}

$(document).ready(function() {
 $('.slide').addClass('is-loaded');

 $('.slideshow .arrows .arrow').on('click',function(){
  slideshowNext($(this).closest('.slideshow'),$(this).hasClass('prev'));
});

 $('.slideshow .pagination .item').on('click',function(){
  slideshowSwitch($(this).closest('.slideshow'),$(this).index());
});

 $('.slideshow .pagination').on('check',function(){
  var slideshow=$(this).closest('.slideshow');
  var pages=$(this).find('.item');
  var index=slideshow.find('.slides .is-active').index();
  pages.removeClass('is-active');
  pages.eq(index).addClass('is-active');
});

/* Lazyloading
$('.slideshow').each(function(){
  var slideshow=$(this);
  var images=slideshow.find('.image').not('.is-loaded');
  images.on('loaded',function(){
    var image=$(this);
    var slide=image.closest('.slide');
    slide.addClass('is-loaded');
  });
*/

 slideshow.on('click', function() {
  clearTimeout($(this).data('timeout'));
  $(this).data('timeout', null);
 });

 runIntroSequence(slideshow, function() {
  var timeout=setTimeout(function(){
    slideshowNext(slideshow,false,true);
  },slideshowDuration);
  slideshow.data('timeout',timeout);
 });
});

if($('.main-content .slideshow').length > 1) {
  $(window).on('scroll',homeSlideshowParallax);
}
