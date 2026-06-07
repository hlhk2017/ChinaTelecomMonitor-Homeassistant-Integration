class CtmTelecomCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("ctm-telecom-card-editor");
  }

  static getStubConfig() {
    return {
      type: "custom:ctm-telecom-card",
      title: "电信套餐",
      balance_warning_below: 20,
      usage_warning_percent: 80,
      usage_danger_percent: 95,
      show_all_entities: false,
    };
  }

  setConfig(config) {
    this.config = {
      title: "电信套餐",
      balance_warning_below: 20,
      usage_warning_percent: 80,
      usage_danger_percent: 95,
      show_all_entities: false,
      ...config,
    };
    if (this.config.device_id === "") delete this.config.device_id;
    this.entities = [];
    this.device = null;
    this.discoveryKey = "";
    this.render();
  }

  connectedCallback() {
    if (this._moreInfoHandler) return;
    this._moreInfoHandler = (event) => {
      const target = event.target.closest("[data-entity-id]");
      if (!target || !this.contains(target)) return;

      const entityId = target.dataset.entityId;
      if (!entityId) return;
      event.stopPropagation();
      this.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId },
        bubbles: true,
        composed: true,
      }));
    };
    this.addEventListener("click", this._moreInfoHandler);
  }

  disconnectedCallback() {
    if (!this._moreInfoHandler) return;
    this.removeEventListener("click", this._moreInfoHandler);
    this._moreInfoHandler = null;
  }

  set hass(hass) {
    this._hass = hass;
    this.discoverEntities();
    this.render();
  }

  getCardSize() {
    return this.config?.show_all_entities ? 6 : 4;
  }

  async discoverEntities() {
    if (!this._hass?.callWS || this.discovering) return;

    const key = JSON.stringify({
      device_id: this.config.device_id,
      states: Object.keys(this._hass.states || {}).length,
    });
    if (this.discoveryKey === key && this.entities.length) return;

    this.discovering = true;
    try {
      const [devices, registry] = await Promise.all([
        this._hass.callWS({ type: "config/device_registry/list" }),
        this._hass.callWS({ type: "config/entity_registry/list" }),
      ]);

      const telecomDevice = this.config.device_id
        ? devices.find((device) => device.id === this.config.device_id)
        : this.findTelecomDevice(devices, registry);
      const deviceId = telecomDevice?.id || this.config.device_id;

      this.device = telecomDevice || null;
      this.entities = registry
        .filter((entry) => entry.device_id === deviceId)
        .filter((entry) => !entry.disabled_by && !entry.hidden_by)
        .filter((entry) => this._hass.states[entry.entity_id])
        .sort((a, b) => this.sortRank(a).localeCompare(this.sortRank(b)));
      this.discoveryKey = key;
    } catch (error) {
      this.discoveryError = error;
    } finally {
      this.discovering = false;
      this.render(true);
    }
  }

  findTelecomDevice(devices, registry) {
    const text = (device) => [
      device.name_by_user,
      device.name,
      device.manufacturer,
      device.model,
    ].filter(Boolean).join(" ");

    const candidates = devices.filter((device) =>
      /CTM|中国电信|电信|china[_ -]?telecom/i.test(text(device))
    );
    return candidates
      .map((device) => ({
        device,
        count: registry.filter((entry) => entry.device_id === device.id && entry.entity_id?.startsWith("sensor.")).length,
      }))
      .sort((a, b) => b.count - a.count)[0]?.device || null;
  }

  sortRank(entry) {
    const name = this.entryName(entry);
    const entityId = entry.entity_id;
    const rank = [
      [/账户余额|zhang_hu_yu_e/, "01"],
      [/本月消费|ben_yue_xiao_fei/, "02"],
      [/积分|ji_fen/, "03"],
      [/流量使用率|liu_liang_shi_yong_lu/, "04"],
      [/流量剩余|liu_liang_sheng_yu/, "05"],
      [/流量已用|liu_liang_yi_yong/, "06"],
      [/流量总量|liu_liang_zong_liang/, "07"],
      [/流量超量|liu_liang_chao_liang/, "08"],
      [/通话使用率|tong_hua_shi_yong_lu/, "09"],
      [/通话剩余|tong_hua_sheng_yu/, "10"],
      [/通话已用|tong_hua_yi_yong/, "11"],
      [/通话总量|tong_hua_zong_liang/, "12"],
    ].find(([pattern]) => pattern.test(name) || pattern.test(entityId))?.[1] || "99";
    return `${rank}-${entityId}`;
  }

  entryName(entry) {
    return entry.name || entry.original_name || this._hass?.states?.[entry.entity_id]?.attributes?.friendly_name || entry.entity_id;
  }

  label(entry) {
    return this.entryName(entry)
      .replace(/^\d{3}[*\d_]+ ?/, "")
      .replace(/^电信/, "")
      .trim();
  }

  state(entityId) {
    return this._hass?.states?.[entityId];
  }

  findEntity(patterns) {
    return this.entities.find((entry) => {
      const text = `${entry.entity_id} ${this.entryName(entry)}`;
      return patterns.some((pattern) => pattern.test(text));
    });
  }

  value(entry) {
    const state = entry && this.state(entry.entity_id);
    if (!state) return "--";
    const unit = state.attributes?.unit_of_measurement || "";
    return `${state.state}${unit ? ` ${unit}` : ""}`;
  }

  numberValue(entry) {
    const state = entry && this.state(entry.entity_id);
    const value = Number.parseFloat(state?.state);
    return Number.isFinite(value) ? value : null;
  }

  render(force = false) {
    if (!this.config) return;
    const key = JSON.stringify({
      config: this.config,
      entities: this.entities.map((entry) => [entry.entity_id, this.state(entry.entity_id)?.state]),
      discovering: this.discovering,
      error: Boolean(this.discoveryError),
    });
    if (!force && this.lastRenderKey === key) return;
    this.lastRenderKey = key;

    const balance = this.findEntity([/账户余额|zhang_hu_yu_e/]);
    const cost = this.findEntity([/本月消费|ben_yue_xiao_fei/]);
    const points = this.findEntity([/积分|ji_fen/]);
    const flowRate = this.findEntity([/流量使用率|liu_liang_shi_yong_lu/]);
    const callRate = this.findEntity([/通话使用率|tong_hua_shi_yong_lu/]);

    this.innerHTML = `
      <ha-card>
        <div class="ctm-card">
          <div class="header">
            <div>
              <div class="title">${this.escape(this.config.title || "电信套餐")}</div>
              <div class="subtitle">${this.escape(this.device?.name_by_user || this.device?.name || "请选择中国电信套餐设备")}</div>
            </div>
            <ha-icon icon="mdi:sim"></ha-icon>
          </div>
          ${this.discoveryError ? `<div class="message">实体读取失败：${this.escape(this.discoveryError.message || this.discoveryError)}</div>` : ""}
          ${this.discovering && !this.entities.length ? `<div class="message">正在读取设备实体...</div>` : ""}
          ${!this.discovering && !this.entities.length ? `<div class="message">未找到可显示实体，请在卡片编辑器选择 CTM 电信套餐设备。</div>` : ""}
          ${this.entities.length ? `
            <div class="summary">
              ${this.metric("账户余额", balance, "mdi:wallet-outline", this.isBalanceLow(balance))}
              ${this.metric("本月消费", cost, "mdi:cash")}
              ${this.metric("积分", points, "mdi:star-circle-outline")}
            </div>
            <div class="meters">
              ${this.progress("流量", flowRate, this.findEntity([/流量剩余|liu_liang_sheng_yu/]), this.findEntity([/流量总量|liu_liang_zong_liang/]))}
              ${this.progress("通话", callRate, this.findEntity([/通话剩余|tong_hua_sheng_yu/]), this.findEntity([/通话总量|tong_hua_zong_liang/]))}
            </div>
            <div class="groups">
              ${this.group("流量", [/流量剩余|流量已用|流量总量|流量超量|liu_liang_(sheng_yu|yi_yong|zong_liang|chao_liang)/])}
              ${this.group("通话", [/通话剩余|通话已用|通话总量|tong_hua_(sheng_yu|yi_yong|zong_liang)/])}
              ${this.config.show_all_entities ? this.group("其他", [/.*/], true) : ""}
            </div>
          ` : ""}
        </div>
        <style>
          .ctm-card {
            --ctm-blue: #005bac;
            --ctm-sky: #00a3e0;
            --ctm-orange: #f59e0b;
            --ctm-red: #e60012;
            --ctm-soft-blue: rgba(0, 91, 172, 0.08);
            --ctm-soft-sky: rgba(0, 163, 224, 0.12);
            padding: 16px;
            color: var(--primary-text-color);
          }
          .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 14px;
          }
          .title {
            font-size: 18px;
            font-weight: 650;
            line-height: 1.2;
          }
          .subtitle {
            color: var(--secondary-text-color);
            font-size: 13px;
            margin-top: 4px;
          }
          .header ha-icon {
            color: var(--ctm-blue);
          }
          .message {
            color: var(--secondary-text-color);
            padding: 12px 0 4px;
          }
          .summary {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            margin-bottom: 12px;
          }
          .metric {
            border: 1px solid rgba(0, 91, 172, 0.18);
            border-radius: 8px;
            background: linear-gradient(180deg, var(--ctm-soft-blue), rgba(255, 255, 255, 0));
            padding: 10px;
            min-width: 0;
          }
          .metric[data-entity-id],
          .clickable-value,
          .entity-row[data-entity-id] {
            cursor: pointer;
          }
          .metric[data-entity-id]:hover,
          .entity-row[data-entity-id]:hover {
            border-color: rgba(0, 91, 172, 0.36);
            box-shadow: 0 2px 8px rgba(0, 91, 172, 0.12);
          }
          .metric ha-icon {
            --mdc-icon-size: 18px;
            color: var(--ctm-blue);
          }
          .metric-label,
          .row-name,
          .meter-top {
            color: var(--secondary-text-color);
            font-size: 12px;
          }
          .metric-value {
            font-size: 16px;
            font-weight: 650;
            line-height: 1.25;
            margin-top: 6px;
            overflow-wrap: anywhere;
          }
          .metric.warning .metric-value {
            color: var(--ctm-red);
          }
          .meters {
            display: grid;
            gap: 10px;
            margin-bottom: 12px;
          }
          .meter-top,
          .meter-detail {
            display: flex;
            justify-content: space-between;
            gap: 12px;
          }
          .meter-detail {
            color: var(--primary-text-color);
            font-size: 12px;
            margin-top: 5px;
          }
          .clickable-value:hover {
            color: var(--ctm-blue);
            text-decoration: underline;
            text-underline-offset: 2px;
          }
          .bar {
            height: 8px;
            background: rgba(0, 91, 172, 0.16);
            border-radius: 999px;
            overflow: hidden;
            margin-top: 6px;
          }
          .fill {
            height: 100%;
            width: var(--value);
            max-width: 100%;
            background: var(--meter-color, linear-gradient(90deg, var(--ctm-blue), var(--ctm-sky)));
            border-radius: inherit;
          }
          .meter.warn {
            --meter-color: var(--ctm-orange);
          }
          .meter.danger {
            --meter-color: var(--ctm-red);
          }
          .meter.warn .meter-rate {
            color: var(--ctm-orange);
            font-weight: 650;
          }
          .meter.danger .meter-rate {
            color: var(--ctm-red);
            font-weight: 650;
          }
          .groups {
            display: grid;
            gap: 10px;
          }
          .group-title {
            font-size: 13px;
            font-weight: 650;
            margin: 4px 0;
            color: var(--ctm-blue);
          }
          .entity-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
          }
          .entity-row {
            background: var(--ctm-soft-sky);
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 8px 10px;
            min-width: 0;
          }
          .row-value {
            font-weight: 600;
            margin-top: 4px;
            overflow-wrap: anywhere;
          }
          @media (max-width: 480px) {
            .ctm-card {
              padding: 14px;
            }
            .summary {
              grid-template-columns: repeat(3, minmax(0, 1fr));
              gap: 6px;
            }
            .entity-grid {
              grid-template-columns: repeat(3, minmax(0, 1fr));
              gap: 6px;
            }
            .metric {
              padding: 8px;
            }
            .metric ha-icon {
              --mdc-icon-size: 16px;
            }
            .metric-label,
            .row-name,
            .meter-top {
              font-size: 11px;
            }
            .metric-value {
              font-size: 14px;
            }
            .entity-row {
              padding: 8px;
            }
            .row-value {
              font-size: 13px;
            }
            .meter-detail {
              font-size: 12px;
            }
          }
          @media (max-width: 360px) {
            .summary,
            .entity-grid {
              gap: 5px;
            }
            .metric,
            .entity-row {
              padding: 7px;
            }
          }
        </style>
      </ha-card>
    `;
  }

  metric(label, entry, icon, warning = false) {
    return `
      <div class="metric${warning ? " warning" : ""}"${this.entityAttr(entry)}>
        <ha-icon icon="${icon}"></ha-icon>
        <div class="metric-label">${this.escape(label)}</div>
        <div class="metric-value">${this.escape(this.value(entry))}</div>
      </div>
    `;
  }

  progress(label, rateEntry, remainEntry, totalEntry) {
    const rate = this.numberValue(rateEntry);
    const percent = rate === null ? 0 : Math.max(0, Math.min(100, rate));
    const level = this.usageLevel(rate);
    return `
      <div class="meter ${level}">
        <div class="meter-top">
          <span>${this.escape(label)}</span>
          ${this.clickableValue(rateEntry, "meter-rate")}
        </div>
        <div class="bar"><div class="fill" style="--value:${percent}%"></div></div>
        <div class="meter-detail">
          <span>剩余 ${this.clickableValue(remainEntry)}</span>
          <span>总量 ${this.clickableValue(totalEntry)}</span>
        </div>
      </div>
    `;
  }

  clickableValue(entry, extraClass = "") {
    const className = `clickable-value${extraClass ? ` ${extraClass}` : ""}`;
    return `<span class="${className}"${this.entityAttr(entry)}>${this.escape(this.value(entry))}</span>`;
  }

  isBalanceLow(entry) {
    const threshold = Number.parseFloat(this.config.balance_warning_below);
    const value = this.numberValue(entry);
    return Number.isFinite(threshold) && threshold > 0 && value !== null && value < threshold;
  }

  usageLevel(value) {
    if (value === null) return "";
    const warning = Number.parseFloat(this.config.usage_warning_percent);
    const danger = Number.parseFloat(this.config.usage_danger_percent);
    if (Number.isFinite(danger) && danger > 0 && value >= danger) return "danger";
    if (
      Number.isFinite(warning)
      && warning > 0
      && value >= warning
      && (!Number.isFinite(danger) || danger <= 0 || warning < danger)
    ) return "warn";
    return "";
  }

  group(title, patterns, includeOnlyUnmatched = false) {
    const alreadyShown = [
      /账户余额|zhang_hu_yu_e/,
      /本月消费|ben_yue_xiao_fei/,
      /积分|ji_fen/,
      /使用率|shi_yong_lu/,
      /流量剩余|流量已用|流量总量|流量超量|liu_liang_(sheng_yu|yi_yong|zong_liang|chao_liang)/,
      /通话剩余|通话已用|通话总量|tong_hua_(sheng_yu|yi_yong|zong_liang)/,
    ];
    const rows = this.entities.filter((entry) => {
      const text = `${entry.entity_id} ${this.entryName(entry)}`;
      if (includeOnlyUnmatched && alreadyShown.some((pattern) => pattern.test(text))) return false;
      return patterns.some((pattern) => pattern.test(text));
    });
    if (!rows.length) return "";
    return `
      <div>
        <div class="group-title">${this.escape(title)}</div>
        <div class="entity-grid">
          ${rows.map((entry) => `
            <div class="entity-row"${this.entityAttr(entry)}>
              <div class="row-name">${this.escape(this.label(entry))}</div>
              <div class="row-value">${this.escape(this.value(entry))}</div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[char]));
  }

  entityAttr(entry) {
    return entry?.entity_id ? ` data-entity-id="${this.escape(entry.entity_id)}"` : "";
  }
}

class CtmTelecomCardEditor extends HTMLElement {
  setConfig(config) {
    this.config = {
      title: "电信套餐",
      balance_warning_below: 20,
      usage_warning_percent: 80,
      usage_danger_percent: 95,
      show_all_entities: false,
      ...config,
    };
    if (this.config.device_id === "") delete this.config.device_id;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) {
      this._form.hass = hass;
      return;
    }
    this.render();
  }

  render() {
    if (!this._hass || !this.config) return;
    if (!this._form) {
      this.innerHTML = `<ha-form></ha-form>`;
      this._form = this.querySelector("ha-form");
      this._form.schema = [
        { name: "title", selector: { text: {} } },
        { name: "device_id", selector: { device: {} } },
        { name: "balance_warning_below", selector: { number: { min: 0, mode: "box", unit_of_measurement: "元" } } },
        { name: "usage_warning_percent", selector: { number: { min: 0, max: 100, mode: "box", unit_of_measurement: "%" } } },
        { name: "usage_danger_percent", selector: { number: { min: 0, max: 100, mode: "box", unit_of_measurement: "%" } } },
        { name: "show_all_entities", selector: { boolean: {} } },
      ];
      this._form.computeLabel = (schema) => ({
        title: "标题",
        device_id: "电信套餐设备",
        balance_warning_below: "余额低于此值标红",
        usage_warning_percent: "使用率提醒百分比",
        usage_danger_percent: "使用率危险百分比",
        show_all_entities: "显示全部实体",
      }[schema.name] || schema.name);
      this._form.addEventListener("value-changed", (event) => {
        event.stopPropagation();
        const nextConfig = { ...this.config, ...event.detail.value };
        if (JSON.stringify(nextConfig) === JSON.stringify(this.config)) return;
        this.config = nextConfig;
        this.dispatchEvent(new CustomEvent("config-changed", {
          detail: { config: this.config },
          bubbles: true,
          composed: true,
        }));
      });
    }
    this._form.hass = this._hass;
    this._form.data = this.config;
  }
}

customElements.define("ctm-telecom-card", CtmTelecomCard);
customElements.define("ctm-telecom-card-editor", CtmTelecomCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ctm-telecom-card",
  name: "CTM 电信卡片",
  description: "选择中国电信套餐设备后自动读取并展示余额、消费、流量和通话实体。",
});
