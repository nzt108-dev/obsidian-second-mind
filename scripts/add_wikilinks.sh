#!/bin/bash
# Add WikiLinks to vault notes for Obsidian Graph View connectivity

VAULT="$HOME/SecondMind"

echo "=== Adding WikiLinks to SecondMind vault ==="

# ─── 1. Link PRD → Architecture within same project ───
for project_dir in "$VAULT"/*/; do
    project=$(basename "$project_dir")
    [[ "$project" == _* ]] && continue  # skip _global, _inbox, _templates

    prd="$project_dir/prd.md"
    arch="$project_dir/architecture.md"
    guide="$project_dir/guidelines.md"
    decisions="$project_dir/decisions.md"
    api="$project_dir/api.md"

    # PRD → links to architecture, guidelines, decisions
    if [ -f "$prd" ]; then
        links=""
        [ -f "$arch" ] && links="$links\n- [[architecture|Архитектура]]"
        [ -f "$guide" ] && links="$links\n- [[guidelines|Гайдлайны]]"
        [ -f "$decisions" ] && links="$links\n- [[decisions|Решения]]"
        [ -f "$api" ] && links="$links\n- [[api|API]]"

        if [ -n "$links" ]; then
            # Check if links section already exists
            if ! grep -q "## Связанные заметки" "$prd"; then
                echo -e "\n\n## Связанные заметки$links" >> "$prd"
                echo "  ✅ $project/prd.md → added links"
            fi
        fi
    fi

    # Architecture → links to PRD, guidelines, global standards
    if [ -f "$arch" ]; then
        links=""
        [ -f "$prd" ] && links="$links\n- [[prd|Требования (PRD)]]"
        [ -f "$guide" ] && links="$links\n- [[guidelines|Гайдлайны]]"
        [ -f "$decisions" ] && links="$links\n- [[decisions|Решения]]"
        links="$links\n- [[_global/coding-standards|Стандарты кодирования]]"
        links="$links\n- [[_global/tech-stack|Технологический стек]]"
        links="$links\n- [[_global/design-principles|Принципы дизайна]]"

        if ! grep -q "## Связанные заметки" "$arch"; then
            echo -e "\n\n## Связанные заметки$links" >> "$arch"
            echo "  ✅ $project/architecture.md → added links"
        fi
    fi

    # Guidelines → links to PRD, architecture
    if [ -f "$guide" ]; then
        links=""
        [ -f "$prd" ] && links="$links\n- [[prd|Требования (PRD)]]"
        [ -f "$arch" ] && links="$links\n- [[architecture|Архитектура]]"
        links="$links\n- [[_global/coding-standards|Стандарты кодирования]]"

        if ! grep -q "## Связанные заметки" "$guide"; then
            echo -e "\n\n## Связанные заметки$links" >> "$guide"
            echo "  ✅ $project/guidelines.md → added links"
        fi
    fi

    # Decisions → links to PRD, architecture
    if [ -f "$decisions" ]; then
        links=""
        [ -f "$prd" ] && links="$links\n- [[prd|Требования (PRD)]]"
        [ -f "$arch" ] && links="$links\n- [[architecture|Архитектура]]"

        if ! grep -q "## Связанные заметки" "$decisions"; then
            echo -e "\n\n## Связанные заметки$links" >> "$decisions"
            echo "  ✅ $project/decisions.md → added links"
        fi
    fi
done

# ─── 2. Global notes → link to projects that use them ───

# coding-standards → link to all projects with architecture
CODING="$VAULT/_global/coding-standards.md"
if [ -f "$CODING" ] && ! grep -q "## Проекты" "$CODING"; then
    echo -e "\n\n## Проекты, использующие эти стандарты" >> "$CODING"
    for project_dir in "$VAULT"/*/; do
        project=$(basename "$project_dir")
        [[ "$project" == _* ]] && continue
        [ -f "$project_dir/architecture.md" ] && echo "- [[$project/architecture|$project]]" >> "$CODING"
    done
    echo "  ✅ _global/coding-standards → linked to projects"
fi

# tech-stack → link to all projects
TECH="$VAULT/_global/tech-stack.md"
if [ -f "$TECH" ] && ! grep -q "## Проекты" "$TECH"; then
    echo -e "\n\n## Проекты" >> "$TECH"
    for project_dir in "$VAULT"/*/; do
        project=$(basename "$project_dir")
        [[ "$project" == _* ]] && continue
        [ -f "$project_dir/prd.md" ] && echo "- [[$project/prd|$project]]" >> "$TECH"
    done
    echo "  ✅ _global/tech-stack → linked to projects"
fi

# design-principles → link to all projects
DESIGN="$VAULT/_global/design-principles.md"
if [ -f "$DESIGN" ] && ! grep -q "## Проекты" "$DESIGN"; then
    echo -e "\n\n## Проекты" >> "$DESIGN"
    for project_dir in "$VAULT"/*/; do
        project=$(basename "$project_dir")
        [[ "$project" == _* ]] && continue
        [ -f "$project_dir/architecture.md" ] && echo "- [[$project/architecture|$project]]" >> "$DESIGN"
    done
    echo "  ✅ _global/design-principles → linked to projects"
fi

# ─── 3. Cross-project links (related projects) ───

# Flutter projects → link to each other
FLUTTER_PROJECTS=(faithly brieftube astro-psiholog norcal-deals content-fabric-saas)
for p in "${FLUTTER_PROJECTS[@]}"; do
    prd="$VAULT/$p/prd.md"
    [ ! -f "$prd" ] && continue
    if ! grep -q "## Похожие проекты" "$prd"; then
        echo -e "\n\n## Похожие проекты (Flutter)" >> "$prd"
        for other in "${FLUTTER_PROJECTS[@]}"; do
            [ "$other" = "$p" ] && continue
            [ -f "$VAULT/$other/prd.md" ] && echo "- [[$other/prd|$other]]" >> "$prd"
        done
        echo "  ✅ $p/prd.md → cross-linked Flutter projects"
    fi
done

# Python/FastAPI projects → link to each other
PYTHON_PROJECTS=(botseller social-leads-parser youtube-parser zillow-parser ai-content-fabric)
for p in "${PYTHON_PROJECTS[@]}"; do
    prd="$VAULT/$p/prd.md"
    [ ! -f "$prd" ] && continue
    if ! grep -q "## Похожие проекты" "$prd"; then
        echo -e "\n\n## Похожие проекты (Python)" >> "$prd"
        for other in "${PYTHON_PROJECTS[@]}"; do
            [ "$other" = "$p" ] && continue
            [ -f "$VAULT/$other/prd.md" ] && echo "- [[$other/prd|$other]]" >> "$prd"
        done
        echo "  ✅ $p/prd.md → cross-linked Python projects"
    fi
done

# Web/Next.js projects → link to each other
WEB_PROJECTS=(nzt108-dev architect-portfolio zillow-landing yt-saas-frontend dance-studio-website)
for p in "${WEB_PROJECTS[@]}"; do
    prd="$VAULT/$p/prd.md"
    [ ! -f "$prd" ] && continue
    if ! grep -q "## Похожие проекты" "$prd"; then
        echo -e "\n\n## Похожие проекты (Web)" >> "$prd"
        for other in "${WEB_PROJECTS[@]}"; do
            [ "$other" = "$p" ] && continue
            [ -f "$VAULT/$other/prd.md" ] && echo "- [[$other/prd|$other]]" >> "$prd"
        done
        echo "  ✅ $p/prd.md → cross-linked Web projects"
    fi
done

# Templates → link to global
for tmpl in "$VAULT"/_templates/*.md; do
    [ ! -f "$tmpl" ] && continue
    if ! grep -q "## Связанные" "$tmpl"; then
        echo -e "\n\n## Связанные\n- [[_global/coding-standards|Стандарты]]\n- [[_global/tech-stack|Стек]]" >> "$tmpl"
        echo "  ✅ $(basename "$tmpl") → linked to global"
    fi
done

echo ""
echo "=== Done! ==="
TOTAL=$(find "$VAULT" -name "*.md" -exec grep -l "\[\[" {} \; | wc -l)
echo "Files with WikiLinks: $TOTAL"
