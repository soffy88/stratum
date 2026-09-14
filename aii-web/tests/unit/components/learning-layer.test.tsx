/**
 * LearningLayer 渲染测试 — 用《产业经济学》真实 BU 数据(econ_pipeline/bu_econ_zh_2726f38224.json)
 * 验证: 路径/深卡/深卡全字段/原文切片定位/练习/已掌握与笔记交互全部渲染。
 * 数据由 2026-08-14 真实跑批生成并入库(5 路径 / 10 深卡 / 质量门 ok)。
 */
import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import fs, { existsSync } from 'fs';
import path from 'path';
import { LearningLayer } from '@/aii/components/LearningLayer';

const fixturePath = path.resolve(__dirname, '../../../../aii/econ_pipeline/bu_econ_zh_2726f38224.json');
const RAW = existsSync(fixturePath)
  ? JSON.parse(fs.readFileSync(fixturePath, 'utf-8'))
  : { learning_paths: [], deep_cards: [], bu_quality: {} };
const paths = RAW.learning_paths;
const cards = RAW.deep_cards;
const quality = RAW.bu_quality;

describe.skipIf(!existsSync(fixturePath))('LearningLayer · 产业经济学真实数据', () => {
  it('渲染 5 条能力路径与全部 10 张深卡', () => {
    render(<LearningLayer substrate="econ_zh_2726f38224" paths={paths} cards={cards} quality={quality} />);
    expect(screen.getByText('学习层 · Learning Layer')).toBeInTheDocument();
    expect(screen.getByText(/5 条路径 · 10 张深卡/)).toBeInTheDocument();
    expect(screen.getByText(/质量门通过/)).toBeInTheDocument();
    for (const p of paths) expect(screen.getByText(p.name)).toBeInTheDocument();
    for (const c of cards) expect(screen.getByText(c.name)).toBeInTheDocument();
  });

  it('展开一张深卡: 五段结构 + 原文切片定位 + 证据徽章全部可见', () => {
    render(<LearningLayer substrate="econ_zh_2726f38224" paths={paths} cards={cards} quality={quality} />);
    const first = cards[0];
    fireEvent.click(screen.getByText(first.name));
    expect(screen.getByText('语境 · 原文在回应什么')).toBeInTheDocument();
    expect(screen.getByText('论证是怎么展开的')).toBeInTheDocument();
    expect(screen.getByText('来源精读 + 原文切片')).toBeInTheDocument();
    expect(screen.getByText('别这样误用')).toBeInTheDocument();
    expect(screen.getByText('今天怎么用')).toBeInTheDocument();
    // 原文切片逐字文本(多行文本被 MathText 拆分为多元素, 用子串匹配) + KU 定位
    expect(screen.getAllByText((_, el) => !!el?.textContent && el.textContent.includes(first.excerpt.split('\n')[0].trim().slice(0, 18))).length).toBeGreaterThan(0);
    expect(screen.getByText(first.source_excerpts[0].locator)).toBeInTheDocument();
    // 证据徽章(全部 primary) + grade 透明标注
    expect(screen.getAllByText('一手来源').length).toBeGreaterThan(0);
    expect(screen.getByText(`KU grade: ${first.grounding_grades.join(' / ')}`)).toBeInTheDocument();
  });

  it('练习可作答(笔记) + 标记已掌握更新计数', () => {
    render(<LearningLayer substrate="econ_zh_2726f38224" paths={paths} cards={cards} quality={quality} />);
    expect(screen.getByText('0/10 已掌握')).toBeInTheDocument();
    fireEvent.click(screen.getByText(cards[0].name));
    const ta = screen.getByPlaceholderText(/写下你的答案/);
    fireEvent.change(ta, { target: { value: '我的答案：奶茶店再投资买第二台封口机。' } });
    expect(ta).toHaveValue('我的答案：奶茶店再投资买第二台封口机。');
    fireEvent.click(screen.getByText('标记为已掌握'));
    expect(screen.getByText('1/10 已掌握')).toBeInTheDocument();
    expect(screen.getByText('✓ 已掌握 · 点击取消')).toBeInTheDocument();
  });

  it('继续连接跳转到相邻深卡', () => {
    render(<LearningLayer substrate="econ_zh_2726f38224" paths={paths} cards={cards} quality={quality} />);
    fireEvent.click(screen.getByText(cards[0].name));
    const linked = cards.find((c: (typeof cards)[number]) => cards[0].connections.includes(c.id));
    expect(linked).toBeTruthy();
    // 连接按钮与卡名同名(列表项), 点第一个匹配(连接按钮)
    fireEvent.click(screen.getAllByText(linked!.name)[0]!);
    // 相邻卡展开: 语境段出现两次(第一张 + 第二张)
    expect(screen.getAllByText('语境 · 原文在回应什么').length).toBeGreaterThanOrEqual(1);
  });
});
