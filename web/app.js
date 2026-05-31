const appName = "Kotoba Forge";

const translations = {
  "zh-Hans": {
    guestPlaygroundTitle: "免费试炼",
    guestPlaygroundCopy: "无需登录，粘贴 YouTube 链接即刻体验字幕生成。仅限短视频。",
    loginPrompt: "已有账号？登录解锁全部功能",
    showLogin: "登录",
    heroEyebrow: "字幕锻炉控制室",
    heroLede: "提交 YouTube 链接，观察字幕每一步炼制，然后下载 SRT 成品。",
    languageLabel: "界面语言",
    healthChecking: "正在检查 API...",
    healthReady: "API 就绪",
    healthDown: "API 不可用",
    inviteEyebrow: "账号登录",
    loginTitle: "进入工房",
    emailLabel: "邮箱",
    passwordLabel: "密码",
    loginButton: "登录",
    operatorEyebrow: "操作者",
    notSignedIn: "未登录",
    minutesLeft: "分钟余额",
    logoutButton: "退出",
    playgroundEyebrow: "Playground",
    playgroundTitle: "先试一个短片",
    playgroundCopy: "免费试炼通道，只处理短视频。先确认字幕和下载效果，再消耗额度。",
    paidWorkspaceEyebrow: "付费工作区",
    paidWorkspaceTitle: "处理完整视频",
    paidWorkspaceCopy: "使用分钟额度运行正式任务，完成后可下载三份 SRT。",
    billingEyebrow: "计费",
    topUpTitle: "充值",
    topUpCopy: "选择套餐，通过 Stripe 安全支付。支持支付宝 / 微信 / 银行卡。",
    starterPackTitle: "Starter",
    starterPackCopy: "30 分钟，用于冒烟测试",
    studioPackTitle: "Studio",
    studioPackCopy: "120 分钟，用于日常上传",
    archivePackTitle: "Archive",
    archivePackCopy: "600 分钟，用于批量处理",
    sourceUrlLabel: "YouTube 链接",
    sourceUrlPlaceholder: "https://www.youtube.com/watch?v=...",
    trialButton: "启动试炼任务",
    paidButton: "消耗额度",
    queueEyebrow: "队列",
    jobsTitle: "任务",
    refreshButton: "刷新",
    currentRoastEyebrow: "当前炼制",
    detailTitle: "任务详情",
    selectJobEmpty: "选择一个任务查看阶段、事件和下载。",
    adminEyebrow: "管理后台",
    adminTitle: "后台热度检查",
    adminRefreshButton: "刷新管理区",
    usersBalancesTitle: "用户与余额",
    allJobsTitle: "全部任务",
    adjustCreditsTitle: "调整额度",
    targetUserIdLabel: "目标用户 ID",
    minutesLabel: "分钟",
    reasonLabel: "原因",
    applyCreditButton: "应用额度变更",
    auditLogsTitle: "审计日志",
    loggedIn: "已登录。",
    trialQueued: "试炼任务已入队。",
    paidQueued: "付费任务已入队。",
    noJobs: "还没有任务。先添加一个短视频试炼。",
    noDownloads: "字幕完成后会显示下载入口。",
    noEvents: "还没有事件记录。",
    noUsers: "还没有用户。",
    noAdminJobs: "系统里还没有任务。",
    noAuditLogs: "还没有管理操作记录。",
    retryQueued: "任务已重新入队。",
    cancelConfirm: "确认取消任务 {jobId}？",
    jobCancelled: "任务已取消。",
    creditsAdjusted: "额度已调整。",
    untitledVideo: "未命名视频",
    unknownDuration: "未知",
    statusMetric: "状态",
    stageMetric: "阶段",
    durationMetric: "时长",
    typeMetric: "类型",
    reservedMetric: "预留",
    consumedMetric: "消耗",
    failureReasonTitle: "失败原因",
    quotaFailureHint: "Gemini API 预付费额度已耗尽。充值 AI Studio 项目或切换可用 API key 后再重试；本任务已退回预留分钟。",
    adjustButton: "调整",
    useUserButton: "使用用户",
    retryButton: "重试",
    cancelButton: "取消",
    tabTrial: "试用",
    tabWork: "工作台",
    tabBilling: "充值",
    tabAdmin: "管理",
    minutesShort: "min",
    ledgerEyebrow: "流水",
    ledgerTitle: "最近交易",
    estimateLabel: "视频时长约 <strong>{minutes}</strong> 分钟，{costInfo}",
    estimateTrial: "试炼通道免费",
    estimatePaid: "将消耗 <strong>{minutes}</strong> 分钟额度",
    estimateOverBalance: "余额不足（缺 {shortfall} min）",
    estimating: "正在预估...",
    statusQueued: "排队中",
    statusRunning: "处理中",
    statusRetrying: "重试中",
    statusSucceeded: "已完成",
    statusFailed: "失败",
    statusCancelled: "已取消",
    statusExpired: "已过期",
    stageCreated: "已创建",
    stageMetadataFetched: "获取信息",
    stageVideoDownloaded: "下载视频",
    stageAudioExtracted: "提取音频",
    stageAsrCompleted: "语音识别",
    stagePrepassCompleted: "预分析",
    stageTranslated: "翻译中",
    stageStructureFixed: "结构修正",
    stageFinalized: "最终化",
    stageCleanupCompleted: "清理完成",
    typePaid: "付费",
    typeTrial: "试炼",
  },
  "zh-Hant": {
    guestPlaygroundTitle: "免費試煉",
    guestPlaygroundCopy: "無需登入，貼上 YouTube 連結即刻體驗字幕生成。僅限短影片。",
    loginPrompt: "已有帳號？登入解鎖全部功能",
    showLogin: "登入",
    heroEyebrow: "字幕鍛爐控制室",
    heroLede: "提交 YouTube 連結，觀察字幕每一步鍛造，然後下載 SRT 成品。",
    languageLabel: "介面語言",
    healthChecking: "正在檢查 API...",
    healthReady: "API 就緒",
    healthDown: "API 無法使用",
    inviteEyebrow: "帳號登入",
    loginTitle: "進入工房",
    emailLabel: "信箱",
    passwordLabel: "密碼",
    loginButton: "登入",
    operatorEyebrow: "操作者",
    notSignedIn: "尚未登入",
    minutesLeft: "分鐘餘額",
    logoutButton: "登出",
    playgroundEyebrow: "Playground",
    playgroundTitle: "先試一支短片",
    playgroundCopy: "免費試煉通道，只處理短影片。先確認字幕和下載效果，再消耗額度。",
    paidWorkspaceEyebrow: "付費工作區",
    paidWorkspaceTitle: "處理完整影片",
    paidWorkspaceCopy: "使用分鐘額度執行正式任務，完成後可下載三份 SRT。",
    billingEyebrow: "計費",
    topUpTitle: "儲值",
    topUpCopy: "選擇套餐，透過 Stripe 安全支付。支援信用卡及國際支付方式。",
    starterPackTitle: "Starter",
    starterPackCopy: "30 分鐘，用於冒煙測試",
    studioPackTitle: "Studio",
    studioPackCopy: "120 分鐘，用於日常上傳",
    archivePackTitle: "Archive",
    archivePackCopy: "600 分鐘，用於批次處理",
    sourceUrlLabel: "YouTube 連結",
    sourceUrlPlaceholder: "https://www.youtube.com/watch?v=...",
    trialButton: "啟動試煉任務",
    paidButton: "消耗額度",
    queueEyebrow: "佇列",
    jobsTitle: "任務",
    refreshButton: "重新整理",
    currentRoastEyebrow: "目前鍛造",
    detailTitle: "任務詳情",
    selectJobEmpty: "選擇一個任務查看階段、事件和下載。",
    adminEyebrow: "管理後台",
    adminTitle: "後台熱度檢查",
    adminRefreshButton: "刷新管理區",
    usersBalancesTitle: "使用者與餘額",
    allJobsTitle: "全部任務",
    adjustCreditsTitle: "調整額度",
    targetUserIdLabel: "目標使用者 ID",
    minutesLabel: "分鐘",
    reasonLabel: "原因",
    applyCreditButton: "套用額度變更",
    auditLogsTitle: "稽核紀錄",
    loggedIn: "已登入。",
    trialQueued: "試煉任務已排入佇列。",
    paidQueued: "付費任務已排入佇列。",
    noJobs: "尚無任務。先加入一支短片試煉。",
    noDownloads: "字幕完成後會顯示下載入口。",
    noEvents: "尚無事件紀錄。",
    noUsers: "尚無使用者。",
    noAdminJobs: "系統中尚無任務。",
    noAuditLogs: "尚無管理操作紀錄。",
    retryQueued: "任務已重新排入佇列。",
    cancelConfirm: "確認取消任務 {jobId}？",
    jobCancelled: "任務已取消。",
    creditsAdjusted: "額度已調整。",
    untitledVideo: "未命名影片",
    unknownDuration: "未知",
    statusMetric: "狀態",
    stageMetric: "階段",
    durationMetric: "時長",
    typeMetric: "類型",
    reservedMetric: "預留",
    consumedMetric: "消耗",
    failureReasonTitle: "失敗原因",
    quotaFailureHint: "Gemini API 預付額度已用完。請儲值 AI Studio 專案或切換可用 API key 後再重試；本任務已退回預留分鐘。",
    adjustButton: "調整",
    useUserButton: "使用使用者",
    retryButton: "重試",
    cancelButton: "取消",
    tabTrial: "試用",
    tabWork: "工作台",
    tabBilling: "儲值",
    tabAdmin: "管理",
    minutesShort: "min",
    ledgerEyebrow: "明細",
    ledgerTitle: "最近交易",
    estimateLabel: "影片長度約 <strong>{minutes}</strong> 分鐘，{costInfo}",
    estimateTrial: "試煉通道免費",
    estimatePaid: "將消耗 <strong>{minutes}</strong> 分鐘額度",
    estimateOverBalance: "餘額不足（缺 {shortfall} min）",
    estimating: "正在預估...",
    statusQueued: "排隊中",
    statusRunning: "處理中",
    statusRetrying: "重試中",
    statusSucceeded: "已完成",
    statusFailed: "失敗",
    statusCancelled: "已取消",
    statusExpired: "已過期",
    stageCreated: "已建立",
    stageMetadataFetched: "取得資訊",
    stageVideoDownloaded: "下載影片",
    stageAudioExtracted: "擷取音訊",
    stageAsrCompleted: "語音辨識",
    stagePrepassCompleted: "預分析",
    stageTranslated: "翻譯中",
    stageStructureFixed: "結構修正",
    stageFinalized: "最終化",
    stageCleanupCompleted: "清理完成",
    typePaid: "付費",
    typeTrial: "試煉",
  },
  en: {
    guestPlaygroundTitle: "Free Trial",
    guestPlaygroundCopy: "No login needed. Paste a YouTube link and try subtitle generation instantly. Short videos only.",
    loginPrompt: "Have an account? Sign in to unlock all features",
    showLogin: "Sign in",
    heroEyebrow: "Subtitle kiln control room",
    heroLede: "Submit a YouTube URL, watch each subtitle stage cook, then download the SRT artifacts.",
    languageLabel: "Language",
    healthChecking: "Checking API...",
    healthReady: "API ready",
    healthDown: "API unavailable",
    inviteEyebrow: "Sign in",
    loginTitle: "Open the kitchen",
    emailLabel: "Email",
    passwordLabel: "Password",
    loginButton: "Login",
    operatorEyebrow: "Operator",
    notSignedIn: "Not signed in",
    minutesLeft: "minutes left",
    logoutButton: "Logout",
    playgroundEyebrow: "Playground",
    playgroundTitle: "Try a short clip first",
    playgroundCopy: "Free trial lane for short videos. Use it to confirm subtitles and downloads before spending credits.",
    paidWorkspaceEyebrow: "Paid workspace",
    paidWorkspaceTitle: "Process the full video",
    paidWorkspaceCopy: "Use credits for real jobs with full pipeline processing and downloadable SRT files.",
    billingEyebrow: "Billing",
    topUpTitle: "Top Up",
    topUpCopy: "Choose a plan and pay securely via Stripe. Alipay / WeChat / cards supported.",
    starterPackTitle: "Starter",
    starterPackCopy: "30 min for smoke tests",
    studioPackTitle: "Studio",
    studioPackCopy: "120 min for regular uploads",
    archivePackTitle: "Archive",
    archivePackCopy: "600 min for batch work",
    sourceUrlLabel: "YouTube URL",
    sourceUrlPlaceholder: "https://www.youtube.com/watch?v=...",
    trialButton: "Start playground job",
    paidButton: "Use credits",
    queueEyebrow: "Queue",
    jobsTitle: "Jobs",
    refreshButton: "Refresh",
    currentRoastEyebrow: "Current roast",
    detailTitle: "Job detail",
    selectJobEmpty: "Select a job to inspect stages and downloads.",
    adminEyebrow: "Admin console",
    adminTitle: "Back office heat check",
    adminRefreshButton: "Refresh admin",
    usersBalancesTitle: "Users & balances",
    allJobsTitle: "All jobs",
    adjustCreditsTitle: "Adjust credits",
    targetUserIdLabel: "Target user id",
    minutesLabel: "Minutes",
    reasonLabel: "Reason",
    applyCreditButton: "Apply credit change",
    auditLogsTitle: "Audit logs",
    loggedIn: "Logged in.",
    trialQueued: "Trial job queued.",
    paidQueued: "Paid job queued.",
    noJobs: "No jobs yet. Add a short trial URL first.",
    noDownloads: "Downloads appear after the subtitle batch is complete.",
    noEvents: "No events recorded yet.",
    noUsers: "No users yet.",
    noAdminJobs: "No jobs in the system yet.",
    noAuditLogs: "No admin actions recorded yet.",
    retryQueued: "Job retry queued.",
    cancelConfirm: "Cancel job {jobId}?",
    jobCancelled: "Job cancelled.",
    creditsAdjusted: "Credits adjusted.",
    untitledVideo: "Untitled video",
    unknownDuration: "unknown",
    statusMetric: "Status",
    stageMetric: "Stage",
    durationMetric: "Duration",
    typeMetric: "Type",
    reservedMetric: "Reserved",
    consumedMetric: "Consumed",
    failureReasonTitle: "Failure reason",
    quotaFailureHint: "Gemini API prepaid credits are depleted. Top up the AI Studio project or switch to a funded API key, then retry; reserved minutes were refunded.",
    adjustButton: "Adjust",
    useUserButton: "Use user",
    retryButton: "Retry",
    cancelButton: "Cancel",
    tabTrial: "Trial",
    tabWork: "Workspace",
    tabBilling: "Billing",
    tabAdmin: "Admin",
    minutesShort: "min",
    ledgerEyebrow: "Ledger",
    ledgerTitle: "Recent transactions",
    estimateLabel: "Video ~<strong>{minutes}</strong> min, {costInfo}",
    estimateTrial: "Free trial lane",
    estimatePaid: "Will use <strong>{minutes}</strong> minutes",
    estimateOverBalance: "Insufficient balance (short {shortfall} min)",
    estimating: "Estimating...",
    statusQueued: "Queued",
    statusRunning: "Running",
    statusRetrying: "Retrying",
    statusSucceeded: "Done",
    statusFailed: "Failed",
    statusCancelled: "Cancelled",
    statusExpired: "Expired",
    stageCreated: "Created",
    stageMetadataFetched: "Fetch info",
    stageVideoDownloaded: "Download",
    stageAudioExtracted: "Extract audio",
    stageAsrCompleted: "ASR",
    stagePrepassCompleted: "Pre-analysis",
    stageTranslated: "Translating",
    stageStructureFixed: "Fix structure",
    stageFinalized: "Finalize",
    stageCleanupCompleted: "Cleanup",
    typePaid: "Paid",
    typeTrial: "Trial",
  },
  ja: {
    heroEyebrow: "字幕鍛造コントロールルーム",
    heroLede: "YouTube URL を投入し、字幕処理の各工程を確認して、SRT をダウンロードします。",
    languageLabel: "表示言語",
    healthChecking: "API を確認中...",
    healthReady: "API 稼働中",
    healthDown: "API 利用不可",
    inviteEyebrow: "ログイン",
    loginTitle: "工房に入る",
    emailLabel: "メール",
    passwordLabel: "パスワード",
    loginButton: "ログイン",
    operatorEyebrow: "オペレーター",
    notSignedIn: "未ログイン",
    minutesLeft: "分の残高",
    logoutButton: "ログアウト",
    playgroundEyebrow: "Playground",
    playgroundTitle: "まず短い動画で試す",
    playgroundCopy: "無料の試用レーンです。クレジットを使う前に字幕とダウンロードを確認できます。",
    paidWorkspaceEyebrow: "有料ワークスペース",
    paidWorkspaceTitle: "フル動画を処理",
    paidWorkspaceCopy: "クレジットを使って正式処理を実行し、完了後に 3 種類の SRT をダウンロードできます。",
    billingEyebrow: "課金",
    topUpTitle: "チャージ",
    topUpCopy: "プランを選んでStripeで安全に支払い。国際カード対応。",
    starterPackTitle: "Starter",
    starterPackCopy: "30 分、スモークテスト向け",
    studioPackTitle: "Studio",
    studioPackCopy: "120 分、通常アップロード向け",
    archivePackTitle: "Archive",
    archivePackCopy: "600 分、まとめ処理向け",
    sourceUrlLabel: "YouTube URL",
    sourceUrlPlaceholder: "https://www.youtube.com/watch?v=...",
    trialButton: "試用タスクを開始",
    paidButton: "クレジット使用",
    queueEyebrow: "キュー",
    jobsTitle: "タスク",
    refreshButton: "更新",
    currentRoastEyebrow: "現在の鍛造",
    detailTitle: "タスク詳細",
    selectJobEmpty: "タスクを選択すると工程、イベント、ダウンロードを確認できます。",
    adminEyebrow: "管理コンソール",
    adminTitle: "バックオフィス確認",
    adminRefreshButton: "管理情報を更新",
    usersBalancesTitle: "ユーザーと残高",
    allJobsTitle: "全タスク",
    adjustCreditsTitle: "クレジット調整",
    targetUserIdLabel: "対象ユーザー ID",
    minutesLabel: "分",
    reasonLabel: "理由",
    applyCreditButton: "クレジット変更を適用",
    auditLogsTitle: "監査ログ",
    loggedIn: "ログインしました。",
    trialQueued: "試用タスクをキューに追加しました。",
    paidQueued: "有料タスクをキューに追加しました。",
    noJobs: "タスクはまだありません。短い試用 URL から始めてください。",
    noDownloads: "字幕処理が完了するとダウンロードが表示されます。",
    noEvents: "イベントはまだ記録されていません。",
    noUsers: "ユーザーはまだいません。",
    noAdminJobs: "システム内にタスクはまだありません。",
    noAuditLogs: "管理操作ログはまだありません。",
    retryQueued: "タスクを再キューしました。",
    cancelConfirm: "タスク {jobId} をキャンセルしますか？",
    jobCancelled: "タスクをキャンセルしました。",
    creditsAdjusted: "クレジットを調整しました。",
    untitledVideo: "無題の動画",
    unknownDuration: "不明",
    statusMetric: "状態",
    stageMetric: "工程",
    durationMetric: "長さ",
    typeMetric: "種類",
    reservedMetric: "予約",
    consumedMetric: "消費",
    failureReasonTitle: "失敗理由",
    quotaFailureHint: "Gemini API のプリペイド残高が不足しています。AI Studio プロジェクトへ入金するか利用可能な API key に切り替えてから再試行してください。予約分は返金済みです。",
    adjustButton: "調整",
    useUserButton: "ユーザー使用",
    retryButton: "再試行",
    cancelButton: "取消",
    tabTrial: "試用",
    tabWork: "ワークスペース",
    tabBilling: "チャージ",
    tabAdmin: "管理",
    minutesShort: "分",
    ledgerEyebrow: "明細",
    ledgerTitle: "最近の取引",
    estimateLabel: "動画の長さは約 <strong>{minutes}</strong> 分、{costInfo}",
    estimateTrial: "試用レーンは無料",
    estimatePaid: "<strong>{minutes}</strong> 分を消費します",
    estimateOverBalance: "残高不足（{shortfall} 分不足）",
    estimating: "見積もり中...",
    statusQueued: "待機中",
    statusRunning: "処理中",
    statusRetrying: "リトライ中",
    statusSucceeded: "完了",
    statusFailed: "失敗",
    statusCancelled: "キャンセル",
    statusExpired: "期限切れ",
    stageCreated: "作成",
    stageMetadataFetched: "情報取得",
    stageVideoDownloaded: "動画ダウンロード",
    stageAudioExtracted: "音声抽出",
    stageAsrCompleted: "音声認識",
    stagePrepassCompleted: "事前分析",
    stageTranslated: "翻訳中",
    stageStructureFixed: "構造修正",
    stageFinalized: "最終化",
    stageCleanupCompleted: "クリーンアップ",
    guestPlaygroundTitle: "無料トライアル",
    guestPlaygroundCopy: "ログイン不要。YouTubeリンクを貼るだけで字幕生成を試せます。短い動画のみ。",
    loginPrompt: "アカウントをお持ちですか？ログインして全機能を解放",
    showLogin: "ログイン",
    typePaid: "有料",
    typeTrial: "試用",
  },
};

const state = {
  user: null,
  billing: null,
  providerStatus: null,
  jobs: [],
  selectedJobId: null,
  pollTimer: null,
  language: preferredLanguage(),
};

const $ = (selector) => document.querySelector(selector);

const nodes = {
  healthDot: $("#health-dot"),
  healthText: $("#health-text"),
  languageSelect: $("#language-select"),
  authPanel: $("#auth-panel"),
  loginForm: $("#login-form"),
  workspace: $("#workspace"),
  userEmail: $("#user-email"),
  balanceMinutes: $("#balance-minutes"),
  logoutButton: $("#logout-button"),
  playgroundForm: $("#playground-form"),
  playgroundSourceUrl: $("#playground-source-url"),
  paidJobForm: $("#paid-job-form"),
  paidSourceUrl: $("#paid-source-url"),
  paidStatusMessage: $("#paid-status-message"),
  refreshButton: $("#refresh-button"),
  jobList: $("#job-list"),
  jobDetail: $("#job-detail"),
  downloadLinks: $("#download-links"),
  eventList: $("#event-list"),
  adminPanel: $("#admin-panel"),
  adminRefreshButton: $("#admin-refresh-button"),
  adminUserList: $("#admin-user-list"),
  adminJobList: $("#admin-job-list"),
  creditAdjustForm: $("#credit-adjust-form"),
  creditUserId: $("#credit-user-id"),
  creditMinutes: $("#credit-minutes"),
  creditReason: $("#credit-reason"),
  auditLogList: $("#audit-log-list"),
  toast: $("#toast"),
  heroBalance: $("#hero-balance"),
  heroBalanceMinutes: $("#hero-balance-minutes"),
  tabButtons: document.querySelectorAll("[role=tab]"),
  tabAdmin: $("#tab-admin"),
  panelTrial: $("#panel-trial"),
  panelWork: $("#panel-work"),
  panelBilling: $("#panel-billing"),
  panelAdmin: $("#panel-admin"),
  playgroundEstimate: $("#playground-estimate"),
  paidEstimate: $("#paid-estimate"),
  ledgerList: $("#ledger-list"),
  accountPanel: $("#account-panel"),
  pricingGrid: $("#pricing-grid"),
  guestSection: null,
  guestForm: null,
  guestUrl: null,
};

function preferredLanguage() {
  const saved = window.localStorage.getItem("kotoba-language");
  if (saved && translations[saved]) {
    return saved;
  }
  const browserLanguage = navigator.language || "en";
  if (browserLanguage.startsWith("zh-TW") || browserLanguage.startsWith("zh-HK")) {
    return "zh-Hant";
  }
  if (browserLanguage.startsWith("zh")) {
    return "zh-Hans";
  }
  if (browserLanguage.startsWith("ja")) {
    return "ja";
  }
  return "en";
}

function t(key, values = {}) {
  const text = (translations[state.language] || translations.en)[key] || translations.en[key] || key;
  return Object.entries(values).reduce(
    (message, [name, value]) => message.replaceAll(`{${name}}`, value),
    text,
  );
}

function applyTranslations() {
  document.documentElement.lang = state.language;
  document.title = appName;
  nodes.languageSelect.value = state.language;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  if (!state.user) {
    nodes.healthText.textContent = t("healthChecking");
  }
}

const API_BASE = "https://kotoba.sakamichi-tools.cfd";

async function api(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const fetchOpts = {
    credentials: "include",
    ...options,
  };
  if (!isFormData && !fetchOpts.headers) {
    fetchOpts.headers = { "Content-Type": "application/json" };
  }
  const response = await fetch(API_BASE + path, fetchOpts);

  if (response.status === 204) {
    return {};
  }

  const contentType = response.headers.get("Content-Type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = payload && payload.error
      ? `${payload.error.code}: ${payload.error.message}`
      : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function setBusy(form, busy) {
  form.querySelectorAll("button, input").forEach((node) => {
    node.disabled = busy;
  });
}

function showToast(message) {
  nodes.toast.textContent = message;
  nodes.toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    nodes.toast.classList.remove("is-visible");
  }, 3600);
}

function setHealth(ok, message) {
  nodes.healthDot.classList.toggle("is-ok", ok);
  nodes.healthDot.classList.toggle("is-bad", !ok);
  nodes.healthText.textContent = message;
}

async function checkHealth() {
  try {
    const health = await api("/healthz");
    setHealth(Boolean(health.ok), t("healthReady"));
  } catch (error) {
    setHealth(false, t("healthDown"));
  }
}

async function restoreSession() {
  try {
    const data = await api("/api/auth/me");
    state.user = data.user;
    await loadWorkspace();
  } catch (error) {
    renderSignedOut();
  }
}

async function login(event) {
  event.preventDefault();
  setBusy(nodes.loginForm, true);
  try {
    const payload = {
      email: $("#email").value.trim(),
      password: $("#password").value.trim(),
    };
    const data = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.user = data.user;
    nodes.loginForm.reset();
    console.log("LOGIN OK, loading workspace...", state.user);
    await loadWorkspace();
    console.log("WORKSPACE LOADED");
    showToast(t("loggedIn"));
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(nodes.loginForm, false);
  }
}

async function logout() {
  try {
    await api("/api/auth/logout", { method: "POST", body: "{}" });
  } catch (error) {
    showToast(error.message);
  } finally {
    state.user = null;
    state.billing = null;
    state.jobs = [];
    state.selectedJobId = null;
    renderSignedOut();
  }
}

async function loadWorkspace() {
  if (nodes.guestSection) {
    nodes.guestSection.style.display = "none";
  }
  nodes.authPanel.classList.add("is-hidden");
  document.querySelector(".landing").style.display = "none";
  document.getElementById("hero-logout").classList.remove("is-hidden");
  nodes.workspace.classList.remove("is-hidden");
  if (nodes.userEmail) nodes.userEmail.textContent = state.user.email;
  nodes.tabAdmin.classList.toggle("is-hidden", state.user.role !== "admin");
  await Promise.all([loadBilling(), loadJobs(), loadAdminIfNeeded()]);
  switchTab("trial");
  startPolling();
}

function renderSignedOut() {
  document.getElementById("hero-logout").classList.add("is-hidden");
  const landing = document.querySelector(".landing"); if (landing) landing.style.display = "";
  stopPolling();
  renderGuestPlayground();
  nodes.workspace.classList.add("is-hidden");
  nodes.heroBalance.classList.add("is-hidden");
  nodes.jobList.innerHTML = "";
  nodes.jobDetail.textContent = t("selectJobEmpty");
  nodes.downloadLinks.innerHTML = "";
  nodes.eventList.innerHTML = "";
  nodes.ledgerList.innerHTML = "";
  nodes.adminPanel.classList.add("is-hidden");
  nodes.adminUserList.innerHTML = "";
  nodes.adminJobList.innerHTML = "";
  nodes.auditLogList.innerHTML = "";
}

async function loadBilling() {
  const billing = await api("/api/billing");
  state.billing = billing;
  state.providerStatus = billing.provider_status || null;
  if (nodes.balanceMinutes) nodes.balanceMinutes.textContent = Number(billing.balance_minutes || 0).toFixed(1);
  nodes.heroBalanceMinutes.textContent = Number(billing.balance_minutes || 0).toFixed(1);
  nodes.heroBalance.classList.remove("is-hidden");
  renderProviderStatus();
  if (billing.ledger) renderLedger(billing.ledger);
}

async function submitJob(event, kind) {
  event.preventDefault();
  if (kind === "paid" && isGeminiUnavailable()) {
    showToast(t("quotaFailureHint"));
    return;
  }
  const endpoint = kind === "paid" ? "/api/jobs" : "/api/playground/jobs";
  const form = kind === "paid" ? nodes.paidJobForm : nodes.playgroundForm;
  const sourceInput = kind === "paid" ? nodes.paidSourceUrl : nodes.playgroundSourceUrl;

  setBusy(form, true);
  try {
    let data;
    // Check if file mode is active
    const fileModeBtn = form.querySelector(".source-mode[data-mode=\"file\"].active");
    if (kind === "paid" && fileModeBtn) {
      const fileInput = document.getElementById("paid-file-input");
      const file = fileInput?.files?.[0];
      if (!file) {
        showToast("请先选择视频文件");
        setBusy(form, false);
        return;
      }
      const fd = new FormData();
      fd.append("file", file);
      data = await api("/api/upload", {
        body: fd,
        method: "POST",
      });
    } else {
      data = await api(endpoint, {
        method: "POST",
        body: JSON.stringify({ source_url: sourceInput.value.trim() }),
      });
    }
    state.selectedJobId = data.job_id;
    form.reset();
    await Promise.all([loadBilling().catch(() => null), loadJobs()]);
    await selectJob(data.job_id);
    showToast(t(kind === "paid" ? "paidQueued" : "trialQueued"));
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(form, false);
  }
}

function renderProviderStatus() {
  const unavailable = isGeminiUnavailable();
  const paidButton = nodes.paidJobForm?.querySelector("button[type='submit']");
  if (paidButton) {
    paidButton.disabled = unavailable;
  }
  if (!nodes.paidStatusMessage) {
    return;
  }
  nodes.paidStatusMessage.classList.toggle("is-hidden", !unavailable);
  nodes.paidStatusMessage.textContent = unavailable ? t("quotaFailureHint") : "";
}

function isGeminiUnavailable() {
  return state.providerStatus?.gemini?.available === false;
}

async function loadJobs() {
  try {
    const data = await api("/api/jobs");
    state.jobs = data.jobs || [];
    renderJobs();
    if (!state.selectedJobId && state.jobs.length) {
      state.selectedJobId = state.jobs[0].id;
      await selectJob(state.selectedJobId);
    }
  } catch (error) {
    if (error.message.includes("AUTH_REQUIRED")) {
      renderSignedOut();
      return;
    }
    showToast(error.message);
  }
}

function renderJobs() {
  if (!state.jobs.length) {
    nodes.jobList.innerHTML = `<p class="empty-state">${escapeHtml(t("noJobs"))}</p>`;
    return;
  }

  nodes.jobList.innerHTML = "";
  state.jobs.forEach((job) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "job-card";
    button.classList.toggle("is-active", job.id === state.selectedJobId);
    button.innerHTML = `
      <h3>${escapeHtml(job.video_title || job.source_url_redacted || t("untitledVideo"))}</h3>
      <div class="meta">${escapeHtml(job.id)}</div>
      <div class=\"stage-pill\">${translateStatus(job.status)} / ${translateStage(job.stage)}</div>
    `;
    button.addEventListener("click", () => selectJob(job.id));
    nodes.jobList.append(button);
  });
}

async function selectJob(jobId) {
  state.selectedJobId = jobId;
  renderJobs();
  try {
    const [jobData, eventData] = await Promise.all([
      api(`/api/jobs/${encodeURIComponent(jobId)}`),
      api(`/api/jobs/${encodeURIComponent(jobId)}/events`),
    ]);
    renderJobDetail(jobData.job);
    renderEvents(eventData.events || []);
  } catch (error) {
    showToast(error.message);
  }
}

function renderJobDetail(job) {
  const duration = job.video_duration_seconds
    ? `${Math.round(job.video_duration_seconds)}s`
    : t("unknownDuration");
  const hint = failureHint(job);
  const failure = job.status === "failed"
    ? `
      <div class="failure-card">
        <span>${escapeHtml(t("failureReasonTitle"))}</span>
        <strong>${escapeHtml(job.error_code || "FAILED")}</strong>
        <p>${escapeHtml(job.error_message || "")}</p>
        ${hint ? `<p class="failure-hint">${escapeHtml(hint)}</p>` : ""}
      </div>
    `
    : "";
  nodes.jobDetail.innerHTML = `
    <h3 class="detail-title">${escapeHtml(job.video_title || t("untitledVideo"))}</h3>
    <div class="detail-grid">
      <div class="metric"><span>${escapeHtml(t("statusMetric"))}</span><strong>${translateStatus(job.status)}</strong></div>
      <div class="metric"><span>${escapeHtml(t("stageMetric"))}</span><strong>${translateStage(job.stage)}</strong></div>
      <div class="metric"><span>${escapeHtml(t("durationMetric"))}</span><strong>${escapeHtml(duration)}</strong></div>
      <div class="metric"><span>${escapeHtml(t("typeMetric"))}</span><strong>${translateType(job.job_type || "paid")}</strong></div>
      <div class="metric"><span>${escapeHtml(t("reservedMetric"))}</span><strong>${minutes(job.reserved_minutes)}</strong></div>
      <div class="metric"><span>${escapeHtml(t("consumedMetric"))}</span><strong>${minutes(job.consumed_minutes)}</strong></div>
    </div>
    ${job.progress_message ? `<p class="progress-msg">${escapeHtml(job.progress_message)}</p>` : ""}
    ${failure}
    ${renderStageProgress(job)}
    <p class="meta">${escapeHtml(job.source_url_redacted || job.source_url || "")}</p>
  `;
  renderDownloads(job);
}

function failureHint(job) {
  const errorText = `${job.error_code || ""} ${job.error_message || ""}`;
  if (
    job.error_code === "GEMINI_QUOTA_EXHAUSTED" ||
    errorText.includes("RESOURCE_EXHAUSTED")
  ) {
    return t("quotaFailureHint");
  }
  return "";
}

function renderDownloads(job) {
  const title = job.video_title || job.id;
  const downloads = [
    { key: "original.srt", label: "原文.srt" },
    { key: "finalized.srt", label: "译文.srt" },
  ];
  const ready = job.status === "succeeded" || job.stage === "cleanup_completed";
  nodes.downloadLinks.innerHTML = "";

  if (!ready) {
    nodes.downloadLinks.innerHTML = `<p class="empty-state">${escapeHtml(t("noDownloads"))}</p>`;
    return;
  }

  downloads.forEach((d) => {
    const btn = document.createElement("button");
    btn.className = "download-link";
    btn.textContent = d.label;
    btn.addEventListener("click", async () => {
      const resp = await api(`/api/jobs/${encodeURIComponent(job.id)}/download/${d.key}`);
      const downloadName = `${title} ${d.label}`;
      const blob = new Blob([resp], { type: "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = downloadName;
      a.click();
      URL.revokeObjectURL(url);
    });
    nodes.downloadLinks.append(btn);
  });
}

function renderEvents(events) {
  if (!events.length) {
    nodes.eventList.innerHTML = `<li>${escapeHtml(t("noEvents"))}</li>`;
    return;
  }

  nodes.eventList.innerHTML = "";
  events.forEach((event) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${escapeHtml(event.stage || "stage")} - ${escapeHtml(event.code || event.level || "event")}</strong>
      <p>${escapeHtml(event.message || "")}</p>
      <time>${escapeHtml(event.created_at || "")}</time>
    `;
    nodes.eventList.append(item);
  });
}

async function loadAdminIfNeeded() {
  if (!state.user || state.user.role !== "admin") {
    return;
  }
  const [usersData, jobsData, auditData] = await Promise.all([
    api("/api/admin/users"),
    api("/api/admin/jobs"),
    api("/api/admin/audit-logs"),
  ]);
  renderAdminUsers(usersData.users || []);
  renderAdminJobs(jobsData.jobs || []);
  renderAuditLogs(auditData.audit_logs || []);
}

function renderAdminUsers(users) {
  if (!users.length) {
    nodes.adminUserList.innerHTML = `<p class="empty-state">${escapeHtml(t("noUsers"))}</p>`;
    return;
  }

  nodes.adminUserList.innerHTML = "";
  users.forEach((user) => {
    const card = document.createElement("article");
    card.className = "admin-card user-card";
    card.innerHTML = `
      <div>
        <h4>${escapeHtml(user.email)}</h4>
        <p class="meta">${escapeHtml(user.id)}</p>
        <span class="stage-pill">${escapeHtml(user.role)} / ${escapeHtml(user.status)}</span>
      </div>
      <div class="admin-actions">
        <strong class="credit-badge">${minutes(user.balance_minutes)}</strong>
        <button type="button" data-user-id="${escapeHtml(user.id)}">${escapeHtml(t("adjustButton"))}</button>
      </div>
    `;
    nodes.adminUserList.append(card);
  });
}

function renderAdminJobs(jobs) {
  if (!jobs.length) {
    nodes.adminJobList.innerHTML = `<p class="empty-state">${escapeHtml(t("noAdminJobs"))}</p>`;
    return;
  }

  nodes.adminJobList.innerHTML = "";
  jobs.forEach((job) => {
    const card = document.createElement("article");
    card.className = "admin-card";
    card.innerHTML = `
      <div>
        <h4>${escapeHtml(job.video_title || job.source_url_redacted || job.id)}</h4>
        <p class="meta">${escapeHtml(job.id)} / user ${escapeHtml(job.user_id || "")}</p>
        <span class="stage-pill">${translateStatus(job.status)} / ${translateStage(job.stage)}</span>
      </div>
      <div class="admin-actions">
        <button type="button" class="ghost" data-admin-action="copy-user" data-user-id="${escapeHtml(job.user_id || "")}">${escapeHtml(t("useUserButton"))}</button>
        <button type="button" data-admin-action="retry" data-job-id="${escapeHtml(job.id)}">${escapeHtml(t("retryButton"))}</button>
        <button type="button" class="ghost" data-admin-action="cancel" data-job-id="${escapeHtml(job.id)}">${escapeHtml(t("cancelButton"))}</button>
      </div>
    `;
    nodes.adminJobList.append(card);
  });
}

function renderAuditLogs(logs) {
  if (!logs.length) {
    nodes.auditLogList.innerHTML = `<li>${escapeHtml(t("noAuditLogs"))}</li>`;
    return;
  }

  nodes.auditLogList.innerHTML = "";
  logs.forEach((log) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${escapeHtml(log.action || "admin_action")}</strong>
      <p>${escapeHtml(log.target_type || "target")} ${escapeHtml(log.target_id || "")}</p>
      <time>${escapeHtml(log.created_at || "")}</time>
    `;
    nodes.auditLogList.append(item);
  });
}

async function handleAdminJobAction(event) {
  const button = event.target.closest("button[data-admin-action]");
  if (!button) {
    return;
  }

  const action = button.dataset.adminAction;
  if (action === "copy-user") {
    nodes.creditUserId.value = button.dataset.userId || "";
    nodes.creditMinutes.focus();
    return;
  }

  const jobId = button.dataset.jobId;
  if (!jobId) {
    return;
  }

  button.disabled = true;
  try {
    if (action === "retry") {
      await api(`/api/admin/jobs/${encodeURIComponent(jobId)}/retry`, {
        method: "POST",
        body: "{}",
      });
      showToast(t("retryQueued"));
    }
    if (action === "cancel") {
      if (!window.confirm(t("cancelConfirm", { jobId }))) {
        return;
      }
      await api(`/api/admin/jobs/${encodeURIComponent(jobId)}`, {
        method: "DELETE",
        body: JSON.stringify({ reason: "cancelled from frontend admin console" }),
      });
      showToast(t("jobCancelled"));
    }
    await Promise.all([loadJobs(), loadAdminIfNeeded()]);
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
  }
}

function handleAdminUserAction(event) {
  const button = event.target.closest("button[data-user-id]");
  if (!button) {
    return;
  }
  nodes.creditUserId.value = button.dataset.userId || "";
  nodes.creditMinutes.focus();
}

async function adjustCredits(event) {
  event.preventDefault();
  setBusy(nodes.creditAdjustForm, true);
  try {
    const userId = nodes.creditUserId.value.trim();
    await api(`/api/admin/users/${encodeURIComponent(userId)}/credits/adjust`, {
      method: "POST",
      body: JSON.stringify({
        minutes: Number(nodes.creditMinutes.value),
        reason: nodes.creditReason.value.trim(),
      }),
    });
    nodes.creditAdjustForm.reset();
    await Promise.all([loadBilling().catch(() => null), loadAdminIfNeeded()]);
    showToast(t("creditsAdjusted"));
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(nodes.creditAdjustForm, false);
  }
}

function startPolling() {
  stopPolling();
  state.pollTimer = window.setInterval(async () => {
    if (!state.user) { return; }
    await loadBilling().catch(() => null);
    await loadJobs();
    if (state.selectedJobId) {
      await selectJob(state.selectedJobId);
    }
    await loadAdminIfNeeded().catch(() => null);
  }, 5000);
}

function stopPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

async function changeLanguage(language) {
  if (!translations[language]) {
    return;
  }
  state.language = language;
  window.localStorage.setItem("kotoba-language", language);
  applyTranslations();
  renderJobs();
  if (!state.user) {
    nodes.jobDetail.textContent = t("selectJobEmpty");
    await checkHealth();
    return;
  }
  await checkHealth();
  if (state.selectedJobId) {
    await selectJob(state.selectedJobId);
  }
  await loadAdminIfNeeded().catch(() => null);
}

function minutes(value) {
  return `${Number(value || 0).toFixed(1)}m`;
}

// ── Status / stage localisation ──
const STATUS_KEYS = {
  queued: "statusQueued", running: "statusRunning", retrying: "statusRetrying",
  succeeded: "statusSucceeded", failed: "statusFailed",
  cancelled: "statusCancelled", expired: "statusExpired",
};
const STAGE_ORDER = [
  "created", "metadata_fetched", "video_downloaded", "audio_extracted",
  "asr_completed", "prepass_completed", "translated", "structure_fixed",
  "finalized", "cleanup_completed",
];
const STAGE_KEYS = {
  created: "stageCreated", metadata_fetched: "stageMetadataFetched",
  video_downloaded: "stageVideoDownloaded", audio_extracted: "stageAudioExtracted",
  asr_completed: "stageAsrCompleted", prepass_completed: "stagePrepassCompleted",
  translated: "stageTranslated", structure_fixed: "stageStructureFixed",
  finalized: "stageFinalized", cleanup_completed: "stageCleanupCompleted",
};
const TYPE_KEYS = { paid: "typePaid", trial: "typeTrial" };

function translateStatus(status) { return t(STATUS_KEYS[status] || status); }
function translateStage(stage) { return t(STAGE_KEYS[stage] || stage); }
function translateType(jobType) { return t(TYPE_KEYS[jobType] || jobType); }

function stageProgressIndex(stage) {
  const idx = STAGE_ORDER.indexOf(stage);
  return idx >= 0 ? idx : -1;
}

// ── Tab switching ──
function switchTab(tabName) {
  nodes.tabButtons.forEach((btn) => {
    const active = btn.dataset.tab === tabName;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", String(active));
  });
  nodes.panelTrial.classList.toggle("is-active", tabName === "trial");
  nodes.panelWork.classList.toggle("is-active", tabName === "work");
  nodes.panelBilling.classList.toggle("is-active", tabName === "billing");
  nodes.panelAdmin.classList.toggle("is-active", tabName === "admin");
  if (tabName === "work") {
    loadJobs();
  }
  if (tabName === "admin") {
    loadAdminIfNeeded().catch(() => null);
  }
}

// ── Estimate cost before submit ──
async function estimateCost(url, kind) {
  const estimateEl = kind === "paid" ? nodes.paidEstimate : nodes.playgroundEstimate;
  if (!url) {
    estimateEl.classList.add("is-hidden");
    return;
  }
  estimateEl.classList.remove("is-hidden");
  estimateEl.textContent = t("estimating");
  try {
    const data = await api(`/api/estimate?source_url=${encodeURIComponent(url)}`);
    const mins = Math.ceil(data.duration_seconds / 60);
    if (kind === "paid") {
      const balance = state.billing ? state.billing.balance_minutes : 0;
      if (mins > balance) {
        estimateEl.innerHTML = t("estimateLabel", { minutes: String(mins), costInfo: t("estimateOverBalance", { shortfall: String(mins - balance) }) });
      } else {
        estimateEl.innerHTML = t("estimateLabel", { minutes: String(mins), costInfo: t("estimatePaid", { minutes: String(mins) }) });
      }
    } else {
      estimateEl.innerHTML = t("estimateLabel", { minutes: String(mins), costInfo: t("estimateTrial") });
    }
  } catch (_e) {
    estimateEl.classList.add("is-hidden");
  }
}

// ── Stage progress bar ──
function renderStageProgress(job) {
  const currentIdx = stageProgressIndex(job.stage);
  if (currentIdx < 0) return "";
  let html = '<div class="stage-track">';
  STAGE_ORDER.forEach((s, i) => {
    let cls = "stage-step";
    if (i < currentIdx) cls += " is-done";
    else if (i === currentIdx && job.status !== "succeeded") cls += " is-active";
    html += `<span class="${cls}" title="${translateStage(s)}"></span>`;
  });
  html += "</div>";
  html += `<p class="stage-label">${translateStage(job.stage)}</p>`;
  return html;
}

// ── Ledger rendering ──
function renderLedger(ledger) {
  if (!ledger || !ledger.length) {
    nodes.ledgerList.innerHTML = `<p class="empty-state">${escapeHtml(t("noEvents"))}</p>`;
    return;
  }
  nodes.ledgerList.innerHTML = ledger.map((row) => {
    const isCredit = row.type === "grant" || row.type === "adjustment";
    const cls = isCredit ? "is-credit" : "is-debit";
    const sign = isCredit ? "+" : "-";
    return `<div class="ledger-row">
      <div><div>${escapeHtml(row.reason)}</div><time>${escapeHtml(row.created_at || "")}</time></div>
      <span class="ledger-amount ${cls}">${sign}${Number(row.minutes).toFixed(1)}m</span>
    </div>`;
  }).join("");
}

// ── Wire up static guest playground ──
function initGuestPlayground() {
  const guestSection = document.getElementById("guest-playground-static");
  const guestForm = document.getElementById("guest-form-static");
  const guestUrl = document.getElementById("guest-url-static");
  if (!guestSection || !guestForm) return;

  nodes.guestSection = guestSection;
  nodes.guestForm = guestForm;
  nodes.guestUrl = guestUrl;

  guestForm.addEventListener("submit", submitGuestJob);
  guestUrl.addEventListener("input", (e) => estimateCost(e.target.value.trim(), "trial"));
  document.getElementById("static-show-login").addEventListener("click", (e) => {
    e.preventDefault();
    guestSection.style.display = "none";
    nodes.authPanel.style.display = "";
    nodes.authPanel.classList.remove("is-hidden");
  });
}

function renderGuestPlayground() {
  if (nodes.guestSection) {
    nodes.guestSection.style.display = "";
  }
}

async function submitGuestJob(event) {
  event.preventDefault();
  setBusy(nodes.guestForm, true);
  try {
    const data = await api("/api/playground/jobs", {
      method: "POST",
      body: JSON.stringify({ source_url: nodes.guestUrl.value.trim() }),
    });
    nodes.guestForm.reset();
    showToast(t("trialQueued") + " (job: " + data.job_id + ")");
  } catch (error) {
    showToast(error.message);
  } finally {
    setBusy(nodes.guestForm, false);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

nodes.loginForm.addEventListener("submit", login);
if (nodes.logoutButton) nodes.logoutButton.addEventListener("click", logout);
document.getElementById("hero-logout")?.addEventListener("click", logout);
nodes.playgroundForm.addEventListener("submit", (event) => submitJob(event, "trial"));
nodes.paidJobForm.addEventListener("submit", (event) => submitJob(event, "paid"));
nodes.languageSelect.addEventListener("change", (event) => {
  changeLanguage(event.target.value).catch((error) => showToast(error.message));
});
nodes.refreshButton.addEventListener("click", async () => {
  await Promise.all([loadBilling().catch(() => null), loadJobs(), loadAdminIfNeeded()]);
  if (state.selectedJobId) {
    await selectJob(state.selectedJobId);
  }
});
nodes.adminRefreshButton.addEventListener("click", () => loadAdminIfNeeded().catch((error) => showToast(error.message)));
nodes.adminUserList.addEventListener("click", handleAdminUserAction);
nodes.adminJobList.addEventListener("click", handleAdminJobAction);
nodes.creditAdjustForm.addEventListener("submit", adjustCredits);

// Tab switching
nodes.tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// Estimate on URL input
nodes.playgroundSourceUrl.addEventListener("input", (e) => {
  estimateCost(e.target.value.trim(), "trial");
});
nodes.paidSourceUrl.addEventListener("input", (e) => {
  estimateCost(e.target.value.trim(), "paid");
});
// Source mode tabs + upload
document.querySelectorAll(".source-mode-tabs").forEach(tabs => {
  tabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".source-mode");
    if (!btn) return;
    const container = tabs.parentElement;
    container.querySelectorAll(".source-mode").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const isFile = btn.dataset.mode === "file";
    container.querySelector(".url-input").style.display = isFile ? "none" : "";
    container.querySelector(".file-input").style.display = isFile ? "" : "none";
    // Toggle required on URL input to avoid browser validation conflict
    const urlInput = container.querySelector("input[type='url']");
    if (urlInput) urlInput.required = !isFile;
  });
});
// Drop zone
const dz = document.getElementById("guest-drop-zone");
const fi = document.getElementById("guest-file-input");
if (dz && fi) {
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("drag-over"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag-over"));
  dz.addEventListener("drop", e => { e.preventDefault(); dz.classList.remove("drag-over"); fi.files = e.dataTransfer.files; updateFileName(); });
  fi.addEventListener("change", updateFileName);
}
function updateFileName() {
  const f = document.getElementById("guest-file-input")?.files?.[0];
  const el = document.getElementById("guest-file-name");
  if (el) el.textContent = f ? f.name : "";
}

// Paid drop zone
const paidDz = document.getElementById("paid-drop-zone");
const paidFi = document.getElementById("paid-file-input");
if (paidDz && paidFi) {
  paidDz.addEventListener("dragover", e => { e.preventDefault(); paidDz.classList.add("drag-over"); });
  paidDz.addEventListener("dragleave", () => paidDz.classList.remove("drag-over"));
  paidDz.addEventListener("drop", e => { e.preventDefault(); paidDz.classList.remove("drag-over"); paidFi.files = e.dataTransfer.files; updatePaidFileName(); });
  paidFi.addEventListener("change", updatePaidFileName);
}
function updatePaidFileName() {
  const f = paidFi?.files?.[0];
  const el = document.getElementById("paid-file-name");
  if (el) el.textContent = f ? f.name : "";
}
// Pricing grid click: copy top-up message
async function handlePricingClick(e) {
  const card = e.target.closest("[data-plan]");
  if (!card || !state.user) return;
  console.log("pricing click", card.dataset.plan, state.user);
  try {
    const data = await api("/api/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ plan: card.dataset.plan, base_url: window.location.origin }),
    });
    window.location.href = data.url;
  } catch (err) {
    showToast(err.message);
  }
}
document.getElementById("pricing-grid")?.addEventListener("click", handlePricingClick);
document.getElementById("subscription-grid")?.addEventListener("click", handlePricingClick);

// Checkout success toast

if (window.location.search.includes("checkout=success")) {
  setTimeout(() => {
    const plan = new URLSearchParams(window.location.search).get("plan") || "";
    showToast(`支付成功！${plan} 套餐额度将在几秒内到账。`);
  }, 1000);
}

applyTranslations();
initGuestPlayground();
checkHealth();
restoreSession();