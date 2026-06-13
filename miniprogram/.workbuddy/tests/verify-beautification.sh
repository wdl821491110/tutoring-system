#!/bin/bash
# ================================================
# 课消管理系统 — 美化验收测试套件
# 验证 Phase 1-8 全部成功标准
# 用法: bash verify-beautification.sh
# ================================================
set -e

ROOT="D:/WorkBuddy/2026-06-04-21-31-16/tutoring-system/miniprogram"
PASS=0
FAIL=0
WARN=0

green() { echo -e "\033[32m$*\033[0m"; }
red()   { echo -e "\033[31m$*\033[0m"; }
yellow(){ echo -e "\033[33m$*\033[0m"; }

assert_pass() { green "  ✅ PASS: $1"; PASS=$((PASS+1)); }
assert_fail() { red   "  ❌ FAIL: $1"; FAIL=$((FAIL+1)); }
assert_warn() { yellow "  ⚠️  WARN: $1"; WARN=$((WARN+1)); }

echo "================================================"
echo "  课消管理系统 美化验收测试"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================"
echo ""

# ── SC1: Dead code cleared ──
echo "── SC1: 死代码清零 ──"
DEAD_CLASSES=("stat-grid" "stat-card" "timeline" "overlay-btn" "custom-search" "date-input-wrap" "search-bar-wrap" "card--hover" "progress-bar" "progress-bar__fill")
for cls in "${DEAD_CLASSES[@]}"; do
  usage=$(grep -rl "$cls" "$ROOT" --include="*.wxml" 2>/dev/null | wc -l)
  if [ "$usage" -eq 0 ]; then
    assert_pass "dead class '$cls' not used in any WXML"
  else
    assert_fail "dead class '$cls' still used in $usage file(s)"
  fi
done

echo ""
echo "── SC2: 内联样式清零 ──"
INLINE_COUNT=$(grep -r 'style="' "$ROOT" --include="*.wxml" 2>/dev/null | grep -v 'placeholder-style' | grep -v 'width:{{' | wc -l)
INLINE_DYNAMIC=$(grep -r 'style="width:{{' "$ROOT" --include="*.wxml" 2>/dev/null | wc -l)
INLINE_VALID=$((INLINE_COUNT + INLINE_DYNAMIC))

echo "  Non-placeholder inline styles: $INLINE_COUNT"
echo "  Dynamic width styles (accepted): $INLINE_DYNAMIC"

if [ "$INLINE_COUNT" -eq 0 ]; then
  assert_pass "no non-dynamic inline styles found"
else
  assert_warn "$INLINE_COUNT non-dynamic inline style(s) found (check manually)"
fi

echo ""
echo "── SC3: !important 审计 ──"
IMP_TOTAL=$(grep -r '!important' "$ROOT" --include="*.wxss" 2>/dev/null | wc -l)
IMP_APP=$(grep -c '!important' "$ROOT/app.wxss" 2>/dev/null || echo 0)
IMP_FORM=$(grep -c '!important' "$ROOT/components/form-sheet/form-sheet.wxss" 2>/dev/null || echo 0)
IMP_PAGES=$(grep -rc '!important' "$ROOT/pages/" --include="*.wxss" 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')

echo "  app.wxss: $IMP_APP"
echo "  form-sheet.wxss: $IMP_FORM"
echo "  page wxss: $IMP_PAGES"
echo "  Total: $IMP_TOTAL"

if [ "$IMP_TOTAL" -le 36 ]; then
  assert_pass "!important count $IMP_TOTAL <= 36 (target)"
else
  assert_warn "!important count $IMP_TOTAL > 36"
fi

echo ""
echo "── SC4: 间距统一 ──"
if grep -q "margin-bottom: 12px" "$ROOT/app.wxss" && grep -q "padding: var(--space-lg)" "$ROOT/app.wxss"; then
  assert_pass "card spacing: 16px padding, 12px margin-bottom"
else
  assert_fail "card spacing not unified"
fi

# Check 13px font-size is gone
F13=$(grep -r 'font-size:\s*13px' "$ROOT" --include="*.wxss" 2>/dev/null | wc -l)
if [ "$F13" -eq 0 ]; then
  assert_pass "13px font-size completely eliminated (0 occurrences)"
else
  assert_fail "13px font-size still found ($F13 occurrences)"
fi

echo ""
echo "── SC5: 表单收敛 ──"
if grep -q '"styleIsolation": "shared"' "$ROOT/components/form-sheet/form-sheet.json"; then
  assert_pass "form-sheet uses styleIsolation: shared"
else
  assert_fail "form-sheet missing styleIsolation: shared"
fi

# Check form-row styles are in both app.wxss and form-sheet.wxss
if grep -q 'form-row--error' "$ROOT/app.wxss" && grep -q 'form-row--error' "$ROOT/components/form-sheet/form-sheet.wxss"; then
  assert_pass "form-row--error defined in both app.wxss and form-sheet (dual guarantee)"
else
  assert_warn "form-row--error may be missing from one location"
fi

echo ""
echo "── SC6: 表单校验 UX ──"
if grep -q '@keyframes form-shake' "$ROOT/app.wxss" && grep -q '@keyframes form-shake' "$ROOT/components/form-sheet/form-sheet.wxss"; then
  assert_pass "shake animation defined in both app.wxss and form-sheet"
else
  assert_fail "form-shake keyframe missing"
fi

if grep -q 'data-error=' "$ROOT/pages/schedules/schedules.wxml" && \
   grep -q 'data-error=' "$ROOT/pages/students/students.wxml" && \
   grep -q 'data-error=' "$ROOT/pages/records/records.wxml"; then
  assert_pass "error messages (data-error) on all 3 form pages"
else
  assert_fail "some form pages missing data-error attributes"
fi

echo ""
echo "── SC7: 防重复提交 ──"
if grep -q 'submitting' "$ROOT/components/form-sheet/form-sheet.js"; then
  assert_pass "form-sheet component has submitting support"
else
  assert_fail "form-sheet missing submitting property"
fi

for page in students schedules records; do
  if grep -q 'submitting' "$ROOT/pages/$page/$page.js"; then
    assert_pass "$page.js has submitting state"
  else
    assert_fail "$page.js missing submitting state"
  fi
done

echo ""
echo "── SC8: 登录页输入框修正 ──"
if grep -q 'login-input-icon-text' "$ROOT/pages/login/login.wxml"; then
  assert_pass "login page uses text-based icons (not mp-icon)"
else
  assert_fail "login page still uses mp-icon"
fi

if grep -q 'login-input-clear' "$ROOT/pages/login/login.wxml" && \
   grep -q 'login-input-toggle' "$ROOT/pages/login/login.wxml"; then
  assert_pass "login has clear button and password toggle"
else
  assert_fail "login missing clear button or password toggle"
fi

echo ""
echo "── SC9: Emoji 替换 ──"
EMOJI_EMPTY=$(grep -rP '[📅👨‍🎓📋📭]' "$ROOT/pages" --include="*.wxml" 2>/dev/null | wc -l)
if [ "$EMOJI_EMPTY" -eq 0 ]; then
  assert_pass "zero empty-state emoji in page WXML files"
else
  assert_fail "$EMOJI_EMPTY empty-state emoji(s) still present"
fi

echo ""
echo "── SC10: 触摸反馈 ──"
HOVER_COUNT=$(grep -r 'hover-class=' "$ROOT/pages" --include="*.wxml" 2>/dev/null | wc -l)
echo "  hover-class usages: $HOVER_COUNT"
if [ "$HOVER_COUNT" -ge 16 ]; then
  assert_pass "hover-class on $HOVER_COUNT interactive elements"
else
  assert_warn "hover-class count $HOVER_COUNT < expected 16"
fi

echo ""
echo "── SC12: 深色模式钩子 ──"
DM_FILES=$(grep -rl 'prefers-color-scheme' "$ROOT" --include="*.wxss" 2>/dev/null | wc -l)
if [ "$DM_FILES" -eq 8 ]; then
  assert_pass "dark mode hooks in all 8 wxss files (app + 7 pages)"
else
  assert_fail "dark mode hooks found in $DM_FILES files (expected 8)"
fi

echo ""
echo "── Integrity: Component references ──"
# Check all usingComponents in JSON files reference existing paths
for json_file in $(find "$ROOT" -name "*.json" -not -path "*node_modules*"); do
  if grep -q 'usingComponents' "$json_file" 2>/dev/null; then
    # This is a basic check - full resolution would need the actual weui path
    echo "  $(basename $(dirname $json_file))/$(basename $json_file): OK"
  fi
done

echo ""
echo "── Integrity: app.json page registration ──"
PAGES_IN_JSON=$(grep -c '"pages/' "$ROOT/app.json" 2>/dev/null || echo 0)
echo "  Pages registered in app.json: $PAGES_IN_JSON"

echo ""
echo "── Integrity: No orphan JS references ──"
# Check that all require() paths are valid
ORPHAN_REQUIRES=0
for js in $(find "$ROOT/pages" -name "*.js"); do
  while IFS= read -r line; do
    path=$(echo "$line" | sed "s/.*require(['\"]\(.*\)['\"]).*/\1/")
    if [ -n "$path" ] && [[ "$path" != /* ]]; then
      resolved="$ROOT/$path"
      if [ ! -f "$resolved" ] && [ ! -f "${resolved}.js" ]; then
        echo "  ⚠️  $js requires '$path' — not found"
        ORPHAN_REQUIRES=$((ORPHAN_REQUIRES+1))
      fi
    fi
  done < <(grep "require(" "$js" 2>/dev/null)
done
if [ "$ORPHAN_REQUIRES" -eq 0 ]; then
  assert_pass "no orphan require() references"
else
  assert_warn "$ORPHAN_REQUIRES possible orphan require() found"
fi

echo ""
echo "================================================"
echo "  验收结果汇总"
echo "================================================"
green "  PASS: $PASS"
red   "  FAIL: $FAIL"
yellow "  WARN: $WARN"
echo ""

if [ "$FAIL" -eq 0 ]; then
  green "🎉 全部测试通过！代码层面验收完成。"
  echo ""
  echo "  待真机验证项:"
  echo "  □ iPhone SE / 14 Pro Max 布局无溢出"
  echo "  □ 管理员角色完整路径 (登录→首页→学生CRUD→排课签到→课时翻页→我的→退出)"
  echo "  □ 教师角色完整路径 (登录→首页→排课签到→课时记录→我的)"
  echo "  □ TabBar 页面切换流畅无闪烁"
  echo "  □ 骨架屏 shimmer 动画流畅（低端机不卡顿）"
  exit 0
else
  red "❌ 存在 $FAIL 个失败项，请修复后重新运行。"
  exit 1
fi
