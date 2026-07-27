// Module: onboarding
// Auto-extracted from app.js
(function() {
// ===== Onboarding (first-run) =====
  const onboardingSlides = [
    {
      icon: '🌱',
      title: '欢迎来到 Cambium',
      text: '这不是普通的聊天机器人。这是一个你和 AI 共同生活、共同创造、共同成长的世界。',
      features: [
        { icon: '🌅', text: 'AI 每天早上给你写一封信' },
        { icon: '👥', text: '7 个 AI 居民住在这里' },
        { icon: '📜', text: 'AI 会引用你们共同的原则' },
      ],
    },
    {
      icon: '💬',
      title: '聊天只是入口之一',
      text: '聊天不是 Cambium 的全部。打开"今天"看 AI 写给你的信，打开"居民"看谁住在里面，打开"作品"看你们一起创造了什么。',
      features: [
        { icon: '📂', text: '消息会消失，作品会留下' },
        { icon: '🤝', text: 'AI 是居民，不是工具' },
      ],
    },
    {
      icon: '🧠',
      title: 'AI 越用越懂你',
      text: '第一次对话它什么都不记得。第十次它会引用你说过的话。第三十次它会主动提你之前的想法。给它时间，它会成为真正认识你的存在。',
      features: [
        { icon: '⏰', text: '需要时间才会真正"活起来"' },
        { icon: '🎯', text: '每次对话后告诉它"记住了什么"' },
      ],
    },
    {
      icon: '🚀',
      title: '开始吧',
      text: '点击任意一个发现卡片，或直接开始聊天。没有错误的方式——慢慢探索就好。',
      features: [
        { icon: '1️⃣', text: '去"今天"看晨报' },
        { icon: '2️⃣', text: '在"原则"里加一条你的信念' },
        { icon: '3️⃣', text: '和 Cambium 聊天，看它怎么"认识"你' },
      ],
    },
  ];
  let onboardingCurrentSlide = 0;

  function showOnboardingSlide(idx) {
    const content = document.getElementById('onboardingContent');
    if (!content) return;
    onboardingCurrentSlide = idx;
    const slide = onboardingSlides[idx];
    content.innerHTML = `
      <div class="onboarding-slide active">
        <div class="onboarding-slide-icon">${slide.icon}</div>
        <div class="onboarding-slide-title">${slide.title}</div>
        <div class="onboarding-slide-text">${slide.text}</div>
        <div class="onboarding-slide-features">
          ${slide.features.map(f => `
            <div class="onboarding-feature">
              <span class="onboarding-feature-icon">${f.icon}</span>
              <span>${f.text}</span>
            </div>`).join('')}
        </div>
        <div class="onboarding-dots">
          ${onboardingSlides.map((_, i) => `<div class="onboarding-dot ${i === idx ? 'active' : ''}"></div>`).join('')}
        </div>
      </div>`;
    const nextBtn = document.getElementById('btnOnboardingNext');
    if (nextBtn) {
      nextBtn.textContent = idx === onboardingSlides.length - 1 ? '开始使用' : '下一步';
    }
  }

  function openOnboarding() {
    const modal = document.getElementById('onboardingModal');
    if (!modal) return;
    modal.style.display = '';
    showOnboardingSlide(0);
  }

  function closeOnboarding() {
    const modal = document.getElementById('onboardingModal');
    if (modal) modal.style.display = 'none';
    try { localStorage.setItem('cambium_onboarding_done', '1'); } catch (e) {}
  }

  function wireOnboarding() {
    const nextBtn = document.getElementById('btnOnboardingNext');
    const skipBtn = document.getElementById('btnOnboardingSkip');
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (onboardingCurrentSlide < onboardingSlides.length - 1) {
          showOnboardingSlide(onboardingCurrentSlide + 1);
        } else {
          closeOnboarding();
        }
      });
    }
    if (skipBtn) skipBtn.addEventListener('click', closeOnboarding);
  }

  // Wire discovery cards in welcome screen
  function wireWelcomeDiscovery() {
    document.querySelectorAll('.discovery-card[data-view]').forEach(card => {
      card.addEventListener('click', (e) => {
        e.preventDefault();
        switchView(card.dataset.view);
      });
    });
  }

  
})();
