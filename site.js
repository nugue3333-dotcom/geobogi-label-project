(function () {
  const products = window.GEOBOKI_PRODUCTS || [];
  const useCases = window.GEOBOKI_USE_CASES || [];
  const params = new URLSearchParams(window.location.search);
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    })[char]);
  }

  function productById(id, useFallback = true) {
    const found = products.find((product) => product.id === id);
    return found || (useFallback ? products.find((product) => product.category === "printer") : null);
  }

  function readCart() {
    try {
      return JSON.parse(localStorage.getItem("geoboki-cart") || "[]");
    } catch {
      return [];
    }
  }

  function writeCart(cart) {
    localStorage.setItem("geoboki-cart", JSON.stringify(cart));
    updateCartCount();
  }

  function updateCartCount() {
    const count = readCart().reduce((sum, item) => sum + (Number(item.qty) || 0), 0);
    $$(".cart-count").forEach((node) => {
      node.textContent = String(count);
    });
  }

  function currentPageName() {
    return document.body.dataset.page || "";
  }

  function initNavigation() {
    const page = currentPageName();
    $$(".site-nav a").forEach((link) => {
      if (link.dataset.page === page) link.setAttribute("aria-current", "page");
    });
  }

  function categoryName(category) {
    return {
      all: "전체 제품",
      printer: "프린터",
      scanner: "스캐너",
      package: "패키지",
      supply: "액세서리"
    }[category] || "전체 제품";
  }

  function productBadge(product) {
    if (product.id === "printer-tsc-dh") return "추천";
    if (product.category === "printer") return product.methods && product.methods.includes("감열") ? "감열" : "열전사";
    if (product.category === "scanner") return product.connections && product.connections.includes("무선") ? "무선" : "유선";
    if (product.category === "package") return "패키지";
    return "소모품";
  }

  function metaItems(product) {
    const primary = product.maker || categoryName(product.category);
    const method = product.methods ? product.methods.join("/") : product.connections ? product.connections.join("/") : "상담";
    const size = product.specs && product.specs[0] ? product.specs[0].replace(/^분류:\s*/, "").replace(/^구성:\s*/, "") : "확인 후 안내";
    return [primary, method, size].slice(0, 3);
  }

  function productCard(product) {
    const featured = product.id === "printer-tsc-dh" || product.id === "package-warehouse-2d";
    const meta = metaItems(product).map((item) => `<span>${escapeHtml(item)}</span>`).join("");
    return `
      <article class="product-card${featured ? " is-featured" : ""}">
        <span class="product-badge">${escapeHtml(productBadge(product))}</span>
        <a class="product-image" href="product-detail.html?id=${encodeURIComponent(product.id)}">
          <img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)} 대표사진" />
        </a>
        <h4>${escapeHtml(product.name)}</h4>
        <p>${escapeHtml(product.summary)}</p>
        <div class="product-meta">${meta}</div>
        <div class="quote-price">견적 확인</div>
        <div class="action-row">
          <a class="btn btn-soft" href="product-detail.html?id=${encodeURIComponent(product.id)}">상세보기</a>
        </div>
      </article>
    `;
  }

  function initProductsPage() {
    const mount = $("#productGroups");
    if (!mount) return;

    const state = {
      category: params.get("category") || "all",
      maker: params.get("maker") || "all",
      method: params.get("method") || "all"
    };

    function matchesMethod(product) {
      if (state.method === "all") return true;
      if (product.methods && product.methods.includes(state.method)) return true;
      if (product.connections && product.connections.includes(state.method)) return true;
      return false;
    }

    function visibleProducts() {
      const categoryOrder = { printer: 0, scanner: 1, package: 2, supply: 3 };
      const priority = ["printer-tsc-dh", "printer-tsc-da", "printer-bixolon-xd5-40", "scanner-zebra-ds2200"];
      return products.filter((product) => {
        if (state.category !== "all" && product.category !== state.category) return false;
        if (state.maker !== "all" && product.maker !== state.maker) return false;
        return matchesMethod(product);
      }).sort((left, right) => {
        const leftPriority = priority.indexOf(left.id);
        const rightPriority = priority.indexOf(right.id);
        if (leftPriority !== -1 || rightPriority !== -1) {
          return (leftPriority === -1 ? 99 : leftPriority) - (rightPriority === -1 ? 99 : rightPriority);
        }
        return (categoryOrder[left.category] ?? 9) - (categoryOrder[right.category] ?? 9);
      });
    }

    function renderControls() {
      $$("[data-category]").forEach((button) => button.classList.toggle("is-active", button.dataset.category === state.category));
      $$("[data-maker]").forEach((button) => button.classList.toggle("is-active", button.dataset.maker === state.maker));
      $$("[data-method]").forEach((button) => button.classList.toggle("is-active", button.dataset.method === state.method));
      const makerFilters = $("#makerFilters");
      const methodFilters = $("#methodFilters");
      if (makerFilters) makerFilters.style.display = state.category === "package" || state.category === "supply" ? "none" : "flex";
      if (methodFilters) methodFilters.style.display = state.category === "package" || state.category === "supply" ? "none" : "flex";
    }

    function render() {
      renderControls();
      const items = visibleProducts();
      const boardTitle = $("#boardTitle");
      const boardSubtitle = $("#boardSubtitle");
      const boardCount = $("#boardCount");
      if (boardTitle) boardTitle.textContent = categoryName(state.category);
      if (boardSubtitle) {
        boardSubtitle.textContent = state.category === "printer"
          ? "감열과 열전사 후보를 구분해 비교합니다."
          : "상세 모델과 구성은 주문서 확인 후 안내합니다.";
      }
      if (boardCount) boardCount.textContent = `${items.length}개`;
      mount.innerHTML = `
        <section class="product-group">
          <div class="product-grid">
            ${items.map(productCard).join("") || `<p class="notice">현재 표시할 제품이 없습니다. 필터를 변경해 주세요.</p>`}
          </div>
        </section>
      `;
    }

    document.addEventListener("click", (event) => {
      const category = event.target.closest("[data-category]");
      if (category) {
        state.category = category.dataset.category;
        if (state.category === "package" || state.category === "supply") {
          state.maker = "all";
          state.method = "all";
        }
        render();
        return;
      }

      const maker = event.target.closest("[data-maker]");
      if (maker) {
        state.maker = maker.dataset.maker;
        if (state.category === "all") state.category = "printer";
        render();
        return;
      }

      const method = event.target.closest("[data-method]");
      if (method) {
        state.method = method.dataset.method;
        render();
      }
    });

    render();
  }

  function initDetailPage() {
    const mount = $("#detailMount");
    if (!mount) return;
    const product = productById(params.get("id"));
    const specs = (product.specs || []).map((spec) => `<div class="spec">${escapeHtml(spec)}</div>`).join("");
    const badges = (product.badges || []).map((badge) => `<span class="chip">${escapeHtml(badge)}</span>`).join("");

    mount.innerHTML = `
      <div class="detail-image">
        <img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)} 대표사진" />
      </div>
      <article class="detail-panel">
        <div class="chip-row">${badges}</div>
        <h1 class="page-title">${escapeHtml(product.name)}</h1>
        <p class="lead">${escapeHtml(product.summary)}</p>
        <div class="spec-grid">${specs}</div>
        <p class="notice">가격, 재고, 배송비, 설치비, 보증·환불 조건은 주문서 확인 후 안내합니다.</p>
        <div class="action-row" style="margin-top:16px">
          <a class="btn btn-primary" href="order.html?product=${encodeURIComponent(product.id)}">이 모델 견적 문의</a>
          <a class="btn btn-secondary" href="products.html">제품 목록으로</a>
        </div>
      </article>
    `;
  }

  function initOrderPage() {
    const mount = $("#orderItems");
    if (!mount) return;
    const incoming = params.get("product");
    const cart = readCart();
    if (incoming && productById(incoming, false)) {
      const item = cart.find((entry) => entry.id === incoming);
      if (item) item.qty = Math.max(1, Number(item.qty) || 1);
      else cart.push({ id: incoming, qty: 1 });
      writeCart(cart);
    }

    function renderCart() {
      const current = readCart().filter((item) => productById(item.id, false));
      if (!current.length) {
        mount.innerHTML = `<p class="notice">선택된 제품이 없습니다. 제품 페이지에서 상세보기 후 견적 문의를 눌러주세요.</p>`;
        updateCartCount();
        return;
      }

      mount.innerHTML = `
        <div class="order-row header">
          <span>상품</span><span>단가</span><span>수량</span><span>금액</span><span></span>
        </div>
        ${current.map((item) => {
          const product = productById(item.id);
          return `
            <div class="order-row">
              <div class="order-product-name">
                <strong>${escapeHtml(product.name)}</strong>
                <span>${escapeHtml(productBadge(product))} · ${escapeHtml(metaItems(product).join(" · "))}</span>
              </div>
              <span>견적 확인</span>
              <span>
                <span class="qty-box">
                  <button type="button" data-dec="${escapeHtml(item.id)}">-</button>
                  <input type="number" min="1" value="${Number(item.qty) || 1}" data-qty="${escapeHtml(item.id)}" aria-label="${escapeHtml(product.name)} 수량" />
                  <button type="button" data-inc="${escapeHtml(item.id)}">+</button>
                </span>
              </span>
              <strong>상담 후 확정</strong>
              <button class="remove-btn" type="button" data-remove="${escapeHtml(item.id)}" aria-label="${escapeHtml(product.name)} 삭제">x</button>
            </div>
          `;
        }).join("")}
      `;
      updateCartCount();
    }

    function updateQty(id, nextQty) {
      const current = readCart();
      const item = current.find((entry) => entry.id === id);
      if (!item) return;
      item.qty = Math.max(1, nextQty);
      writeCart(current);
      renderCart();
    }

    document.addEventListener("input", (event) => {
      const qty = event.target.closest("[data-qty]");
      if (!qty) return;
      updateQty(qty.dataset.qty, Number.parseInt(qty.value, 10) || 1);
    });

    document.addEventListener("click", (event) => {
      const inc = event.target.closest("[data-inc]");
      if (inc) {
        const item = readCart().find((entry) => entry.id === inc.dataset.inc);
        updateQty(inc.dataset.inc, (Number(item && item.qty) || 1) + 1);
        return;
      }

      const dec = event.target.closest("[data-dec]");
      if (dec) {
        const item = readCart().find((entry) => entry.id === dec.dataset.dec);
        updateQty(dec.dataset.dec, (Number(item && item.qty) || 1) - 1);
        return;
      }

      const remove = event.target.closest("[data-remove]");
      if (!remove) return;
      writeCart(readCart().filter((item) => item.id !== remove.dataset.remove));
      renderCart();
    });

    const form = $("#orderForm");
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const success = $("#orderSuccess");
        const selected = readCart().map((item) => {
          const product = productById(item.id);
          return `${product.name} ${item.qty}개`;
        }).join(", ");
        success.textContent = `견적 요청 화면이 준비되었습니다. 선택 제품: ${selected || "없음"}. 가격, 재고, 설치지원, 배송 조건 확인 후 결제 안내가 필요합니다.`;
        success.classList.add("is-visible");
      });
    }

    renderCart();
  }

  function renderTemplate(useCase) {
    const labelTitle = $("#labelTitle");
    const labelFields = $("#labelFields");
    const dataPreview = $("#dataPreview");
    if (!labelTitle || !labelFields || !dataPreview || !useCase) return;

    labelTitle.textContent = useCase.title.replace(" 라벨", "");
    const fields = useCase.fields.slice(0, 4);
    labelFields.innerHTML = `
      <div>분류</div><div>${escapeHtml(useCase.sample)}</div><div>코드</div>
      <div>${escapeHtml(fields[0] || "제품명")}</div><div>데이터 연결</div><div>검증</div>
    `;
    dataPreview.innerHTML = `
      <div class="data-row"><span>제품코드</span><span>제품명</span><span>모델명</span><span>바코드</span><span>QR 데이터</span></div>
      ${fields.map((field, index) => `
        <div class="data-row">
          <span>P10${index + 1}</span><span>${escapeHtml(field)}</span><span>${escapeHtml(useCase.sample)}</span><span>88091234567${index}</span><span>${escapeHtml(useCase.id)}-${index + 1}</span>
        </div>
      `).join("")}
    `;
    $$("[data-template]").forEach((button) => button.classList.toggle("is-active", button.dataset.template === useCase.id));
  }

  function initProgramPage() {
    if (!$("#labelTitle")) return;

    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-template]");
      if (!button) return;
      const selected = useCases.find((useCase) => useCase.id === button.dataset.template) || useCases[0];
      renderTemplate(selected);
    });

    renderTemplate(useCases[0]);
  }

  initNavigation();
  updateCartCount();
  initProductsPage();
  initDetailPage();
  initOrderPage();
  initProgramPage();
})();
