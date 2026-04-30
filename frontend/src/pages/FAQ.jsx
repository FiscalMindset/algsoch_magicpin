import React from 'react';
import Card from '../components/Card';
import './FAQ.css';

function FAQ() {
  return (
    <div className="faq-page">
      <div className="faq-header">
        <h2>🧾 Before You Submit</h2>
        <p>Straight answers (so you don’t overfit the simulator)</p>
      </div>

      <div className="faq-grid">
        <Card title="Straight answer">
          <p className="faq-text">
            This challenge is a direct quality filter: sharp reasoning, strong product judgment, and reliable execution.
          </p>
        </Card>

        <Card title="Simulator vs Exam">
          <p className="faq-text">
            The local <span className="mono">judge_simulator</span> gives you a deterministic dry-run on the 30 canonical
            test pairs. The actual judge harness uses the same scoring logic but injects new facts you haven&apos;t seen —
            fresh digest items, performance shifts, surprise customer scopes, replies you can&apos;t predict.
          </p>
          <p className="faq-text">
            Your score depends on how your bot handles those, not on how it does on the 30 pairs. Bots that
            pattern-match the simulator will fail. Bots that ground every output in the context they&apos;ve actually been
            given will not.
          </p>
        </Card>

        <Card title="What we actually care about">
          <p className="faq-text">
            Signal quality. If your decisions are grounded, deterministic, and useful for merchants, we notice.
          </p>
        </Card>

        <Card title="What the prize really is">
          <p className="faq-text">
            A full-time offer — or an internship that converts into a full-time offer. Top candidates join the team;
            strong performance turns it into a permanent role.
          </p>
        </Card>

        <Card title="How hard is the challenge?">
          <p className="faq-text">
            Building the bot is easy. Building one a merchant actually wants to engage with is the hard part — that’s
            the filter.
          </p>
        </Card>
      </div>
    </div>
  );
}

export default FAQ;

