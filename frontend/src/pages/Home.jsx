import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { productsApi, categoriesApi } from '../api/client';
import { useCart } from '../context/CartContext';
import '../styles/home.css';

/* ---- local fallback data (used if the API is unreachable; easy to swap) ---- */
const EMOJIS = ['🎁', '🌸', '🍫', '🧸', '🕯️', '💐', '🎂', '☕', '💎', '🎀', '🍷', '📿'];
const FALLBACK_PRODUCTS = [
  { id: -1, name: 'Birthday Surprise Box', price: 1299, old: 1799, emoji: '🎂', rating: 4.9, badge: 'best', occasion: 'birthday' },
  { id: -2, name: 'Rose & Chocolate Hamper', price: 1499, old: 1999, emoji: '🌹', rating: 4.8, badge: 'sale', occasion: 'anniversary' },
  { id: -3, name: 'Luxury Spa Kit', price: 2199, old: null, emoji: '🧖', rating: 4.7, badge: 'new', occasion: 'wedding' },
  { id: -4, name: 'Gourmet Coffee Set', price: 899, old: 1199, emoji: '☕', rating: 4.6, badge: 'sale', occasion: 'corporate' },
  { id: -5, name: 'Scented Candle Trio', price: 749, old: null, emoji: '🕯️', rating: 4.8, badge: 'custom', occasion: 'birthday' },
  { id: -6, name: 'Premium Flower Bouquet', price: 1099, old: 1399, emoji: '💐', rating: 4.9, badge: 'best', occasion: 'flowers' },
  { id: -7, name: 'Artisan Chocolate Box', price: 999, old: null, emoji: '🍫', rating: 4.7, badge: 'new', occasion: 'anniversary' },
  { id: -8, name: 'Teddy & Balloons Combo', price: 1599, old: 2099, emoji: '🧸', rating: 4.8, badge: 'sale', occasion: 'birthday' },
];
const OCCASIONS = [
  { key: 'all', label: 'All', slug: '' }, { key: 'birthday', label: '🎂 Birthday', slug: 'birthday' },
  { key: 'anniversary', label: '💕 Anniversary', slug: 'anniversary' }, { key: 'wedding', label: '💍 Wedding', slug: 'wedding' },
  { key: 'flowers', label: '🌸 Flowers', slug: 'flowers' }, { key: 'corporate', label: '💼 Corporate', slug: 'corporate' },
];
const HAMPER_ITEMS = [['🍫', 'Chocolates'], ['🧴', 'Skincare'], ['🕯️', 'Candles'], ['☕', 'Tea & Coffee'], ['📚', 'Books'], ['💐', 'Flowers']];
const FEATURES = [['🚚', '60-Min Delivery', 'Same-day in metro cities'], ['🎀', 'Free Gift Wrap', 'Premium boxes & ribbons'],
  ['🔄', 'Easy Returns', '7-day hassle-free returns'], ['🔒', 'Secure Payments', 'UPI · Cards · COD']];
const BUDGETS = ['Under ₹500', '₹500–₹1500', '₹1500–₹3000', '₹3000+'];

const inr = (v) => '₹' + Number(v || 0).toLocaleString('en-IN');

export default function Home() {
  const navigate = useNavigate();
  const { add } = useCart();
  const [products, setProducts] = useState(FALLBACK_PRODUCTS);
  const [occasion, setOccasion] = useState('all');
  const [budget, setBudget] = useState(1);
  const [hamper, setHamper] = useState([]);
  const [news, setNews] = useState(''); const [newsOk, setNewsOk] = useState(false);
  const toastRef = useRef(null); const starsRef = useRef(null);

  /* twinkling stars */
  useEffect(() => {
    const host = starsRef.current; if (!host) return;
    for (let i = 0; i < 90; i++) {
      const s = document.createElement('div'); s.className = 'star';
      const sz = Math.random() * 2.2 + 0.6;
      s.style.width = s.style.height = sz + 'px';
      s.style.left = Math.random() * 100 + '%'; s.style.top = Math.random() * 100 + '%';
      s.style.animationDuration = (Math.random() * 4 + 2) + 's';
      s.style.animationDelay = (Math.random() * 4) + 's';
      host.appendChild(s);
    }
    return () => { host.innerHTML = ''; };
  }, []);

  /* products — real API with fallback; refetch on occasion change */
  useEffect(() => {
    const occ = OCCASIONS.find((o) => o.key === occasion);
    const params = occ?.slug ? { category: occ.slug, limit: 12 } : { sort: 'rating', limit: 12 };
    productsApi.list(params).then((r) => {
      const items = r.data.items || [];
      if (!items.length) { if (occasion !== 'all') setProducts([]); return; }
      setProducts(items.map((p, i) => ({
        id: p.id, raw: p, name: p.name,
        price: Number(p.discount_price ?? p.price), old: p.discount_price ? Number(p.price) : null,
        image: p.image_url || null, emoji: EMOJIS[i % EMOJIS.length], rating: Number(p.rating_avg) || 4.7,
        badge: p.discount_price ? 'sale' : p.is_quick_delivery ? 'best' : p.is_customizable ? 'custom' : 'new',
      })));
    }).catch(() => {
      // offline: filter the local fallback set
      setProducts(occ?.slug ? FALLBACK_PRODUCTS.filter((p) => p.occasion === occ.key) : FALLBACK_PRODUCTS);
    });
  }, [occasion]);

  /* scroll reveal + stat count-up */
  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        const delay = Number(en.target.dataset.i || 0) * 85;
        setTimeout(() => en.target.classList.add('vis'), delay);
        if (en.target.dataset.count) countUp(en.target);
        io.unobserve(en.target);
      });
    }, { threshold: 0.15 });
    document.querySelectorAll('.wb-home .rev').forEach((el, i) => { el.dataset.i = i % 6; io.observe(el); });
    document.querySelectorAll('.wb-home [data-count]').forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [products]);

  const toast = (msg) => {
    const t = toastRef.current; if (!t) return;
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('show'), 2400);
  };

  const tilt = (e, max = 22) => {
    const c = e.currentTarget, r = c.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    c.style.transform = `perspective(700px) rotateY(${x * max}deg) rotateX(${-y * max}deg) translateZ(10px)`;
    c.style.setProperty('--mx', ((x + 0.5) * 100) + '%'); c.style.setProperty('--my', ((y + 0.5) * 100) + '%');
  };
  const untilt = (e) => { e.currentTarget.style.transform = ''; };

  const burst = (x, y) => {
    const colors = ['#a855f7', '#ec4899', '#ff7040', '#fbbf24', '#34d399'];
    for (let i = 0; i < 24; i++) {
      const p = document.createElement('div'); p.className = 'wb-particle';
      p.style.left = x + 'px'; p.style.top = y + 'px'; p.style.background = colors[i % colors.length];
      document.body.appendChild(p);
      const ang = (Math.PI * 2 * i) / 24 + Math.random(), dist = 55 + Math.random() * 85;
      p.animate([{ transform: 'translate(0,0) scale(1)', opacity: 1 },
        { transform: `translate(${Math.cos(ang) * dist}px,${Math.sin(ang) * dist}px) scale(0)`, opacity: 0 }],
        { duration: 700 + Math.random() * 300, easing: 'cubic-bezier(.22,1,.36,1)' }).onfinish = () => p.remove();
    }
  };

  const addToCart = (prod, e) => {
    burst(e.clientX, e.clientY);
    const payload = prod.raw || { id: prod.id, name: prod.name, price: prod.price, discount_price: null, slug: '#', image_url: null };
    Promise.resolve(add(payload, 1)).catch(() => {});
    toast(`Added “${prod.name}” to cart 🎉`);
  };

  const toggleHamper = (label) => setHamper((h) => h.includes(label) ? h.filter((x) => x !== label) : [...h, label]);
  const subscribe = (e) => { e.preventDefault(); if (news.includes('@')) { setNewsOk(true); setNews(''); } };

  return (
    <div className="wb-home">
      <div className="bg">
        <div className="blob b1" /><div className="blob b2" /><div className="blob b3" /><div className="blob b4" />
        <div className="stars-host" ref={starsRef} />
      </div>

      <div className="content">
        {/* HERO */}
        <section className="sec hero">
          <div className="rev">
            <span className="tag">✨ India's most-loved gifting platform</span>
            <h1>Gifting, <em>reinvented</em> for every celebration.</h1>
            <p className="sub">Curated hampers, personalized gifts and same-day delivery — wrapped with a little extra magic. 🎁</p>
            <div className="cta-row">
              <button className="btn btn-grad" onClick={() => navigate('/shop')}>Shop the collection</button>
              <button className="btn btn-glass" onClick={() => navigate('/gift-finder')}>✨ Find a gift</button>
            </div>
          </div>

          <div className="box-stage rev" data-i="1">
            <div className="orb" />
            <div className="gbox">
              <div className="gf gf-fr" /><div className="gf gf-bk" /><div className="gf gf-rt" />
              <div className="gf gf-lt" /><div className="gf gf-tp">🎀</div><div className="gf gf-bt" />
            </div>
            <div className="box-shadow" />
            <span className="fbadge f1">⚡ 60-Min Delivery</span>
            <span className="fbadge f2">⭐ 4.9 Rated</span>
            <span className="fbadge f3">🎀 Gift Wrapping</span>
            <span className="fbadge f4">🔄 Easy Returns</span>
          </div>
        </section>

        {/* TRUST STRIP */}
        <section className="sec" style={{ paddingTop: 0 }}>
          <div className="trust glass rev" style={{ borderRadius: 20, padding: 8 }}>
            {[['🚚', 'Free Delivery', 'On orders over ₹999'], ['🔒', 'Secure Checkout', 'UPI · Cards · COD'],
              ['🎀', 'Free Gift Wrap', 'On every order'], ['💬', '24×7 Support', 'We reply fast']].map(([ic, t, s]) => (
              <div className="tcell" key={t}><span className="ic">{ic}</span><div><b>{t}</b><span>{s}</span></div></div>
            ))}
          </div>
        </section>

        {/* PRODUCTS + OCCASION FILTER */}
        <section className="sec">
          <div className="rev"><div className="eyebrow">Shop by occasion</div><h2 className="h2">Gifts they'll <span className="grad-text">never forget</span></h2></div>
          <div className="pills rev" data-i="1">
            {OCCASIONS.map((o) => (
              <button key={o.key} className={`pill3d ${occasion === o.key ? 'active' : ''}`} onClick={() => setOccasion(o.key)}>{o.label}</button>
            ))}
          </div>
          <div className="grid">
            {products.length === 0 && <p style={{ color: 'var(--h-muted)' }}>No products in this occasion yet.</p>}
            {products.map((p) => (
              <div className="pcard rev" key={p.id} onMouseMove={(e) => tilt(e)} onMouseLeave={untilt}>
                <div className="shine" />
                <div className="pimg" style={{ background: p.image ? `url(${p.image})` : `linear-gradient(135deg, #2a0a45, #3a1060)`, backgroundSize: 'cover' }}>
                  {!p.image && (p.emoji || '🎁')}
                  <div className="chips">
                    {p.badge === 'new' && <span className="chip new">NEW</span>}
                    {p.badge === 'sale' && <span className="chip sale">SALE</span>}
                    {p.badge === 'custom' && <span className="chip custom">CUSTOM</span>}
                    {p.badge === 'best' && <span className="chip best">BEST SELLER</span>}
                  </div>
                  <button className="wish" title="Wishlist" onClick={() => toast('Saved to wishlist 🤍')}>🤍</button>
                </div>
                <div className="pbody">
                  <h4>{p.name}</h4>
                  <div className="rating">{'★'.repeat(Math.round(p.rating))} <span style={{ color: 'var(--h-muted)' }}>{p.rating.toFixed(1)}</span></div>
                  <div className="priceline">
                    <span className="now">{inr(p.price)}</span>
                    {p.old && <span className="old">{inr(p.old)}</span>}
                    {p.old && <span className="off">{Math.round((1 - p.price / p.old) * 100)}% off</span>}
                  </div>
                  <button className="add" onClick={(e) => addToCart(p, e)}>Add to Cart</button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* STATS */}
        <section className="sec">
          <div className="stats">
            {[['50000', '50k+', 'Happy customers'], ['4.9', '4.9★', 'Average rating'],
              ['120000', '120k+', 'Gifts delivered'], ['99', '99%', 'On-time delivery']].map(([val, , lbl], i) => (
              <div className="stat rev" key={lbl} data-i={i}>
                <div className="num grad-text" data-count={val} data-target={val}>0</div>
                <div className="lbl">{lbl}</div>
              </div>
            ))}
          </div>
        </section>

        {/* FEATURES */}
        <section className="sec">
          <div className="rev"><div className="eyebrow">The WishBox promise</div><h2 className="h2">Why gift with <span className="grad-text">us</span></h2></div>
          <div className="feats">
            {FEATURES.map(([ic, t, s], i) => (
              <div className="fcard rev" key={t} data-i={i}><span className="fic">{ic}</span><b>{t}</b><span>{s}</span></div>
            ))}
          </div>
        </section>

        {/* AI GIFT FINDER */}
        <section className="sec ai">
          <div className="rev">
            <div className="eyebrow">Powered by WishBox AI</div>
            <h2 className="h2">Not sure what to <span className="grad-text">gift?</span></h2>
            <p style={{ color: 'var(--h-muted)', maxWidth: 420 }}>Tell us who it's for and your budget — our gift finder curates the perfect match in seconds.</p>
            <button className="btn btn-gold" style={{ marginTop: 18 }} onClick={() => navigate('/gift-finder')}>Try the Gift Finder →</button>
          </div>
          <div className="aicard rev" data-i="1" onMouseMove={(e) => tilt(e, 16)} onMouseLeave={untilt}>
            <div className="eyebrow">Describe your gift</div>
            <div className="field">“A thoughtful anniversary gift for my wife who loves spa days…”</div>
            <div className="budgets">
              {BUDGETS.map((b, i) => (
                <span key={b} className={`budget ${budget === i ? 's' : ''}`} onClick={() => setBudget(i)}>{b}</span>
              ))}
            </div>
            <div className="airesult"><span className="ae">🧖</span><div style={{ flex: 1 }}><b>Luxury Spa Hamper</b><span>Perfect match · 96% confidence</span></div><b>{inr(2199)}</b></div>
          </div>
        </section>

        {/* HAMPER BUILDER */}
        <section className="sec">
          <div className="rev" style={{ marginBottom: 20 }}><div className="eyebrow">Make it personal</div><h2 className="h2">Build your own <span className="grad-text">hamper</span></h2></div>
          <div className="hamper rev" data-i="1">
            <div>
              <h3 style={{ fontSize: 22, fontWeight: 800, marginBottom: 10 }}>Pick what they love 🎁</h3>
              <p style={{ color: 'var(--h-muted)', marginBottom: 16 }}>Choose your items, we'll wrap them into one beautiful box.</p>
              <p style={{ color: 'var(--h-muted)' }}>{hamper.length ? `${hamper.length} item(s): ${hamper.join(', ')}` : 'Nothing selected yet.'}</p>
              <button className="btn btn-grad" style={{ marginTop: 16 }} onClick={() => navigate('/hamper-builder')}>Open the builder →</button>
            </div>
            <div className="htiles">
              {HAMPER_ITEMS.map(([ic, label]) => (
                <div key={label} className={`htile ${hamper.includes(label) ? 's' : ''}`} onClick={() => toggleHamper(label)}>
                  <span className="hic">{ic}</span><span>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* FESTIVE BANNER */}
        <section className="sec">
          <div className="festive rev">
            <h3>🔥 Festive Sale is LIVE</h3>
            <p>Up to 40% off on hampers, flowers & personalized gifts. Limited time only.</p>
            <button className="btn-outline" onClick={() => navigate('/shop')}>Grab the deals</button>
          </div>
        </section>

        {/* NEWSLETTER */}
        <section className="sec">
          <div className="news glass rev">
            <div className="eyebrow">Stay in the loop</div>
            <h2 className="h2" style={{ fontSize: 26 }}>Get <span className="grad-text">10% off</span> your first order</h2>
            <form className="nrow" onSubmit={subscribe}>
              <input type="email" placeholder="you@email.com" value={news} onChange={(e) => { setNews(e.target.value); setNewsOk(false); }} />
              <button className="btn btn-grad" type="submit">Subscribe</button>
            </form>
            {newsOk && <p className="ok">🎉 You're in! Check your inbox for the code.</p>}
          </div>
        </section>

        {/* IN-HOME FOOTER STRIP */}
        <div className="hfoot rev">
          <div>
            <div style={{ fontWeight: 800, fontSize: 18 }} className="grad-text">🎁 WishBox</div>
            <p style={{ color: 'var(--h-muted)', fontSize: 13, marginTop: 8, maxWidth: 240 }}>Gifts that say it perfectly — curated, personalized, delivered with care.</p>
            <div className="pays">{['UPI', 'VISA', 'MC', 'PayTM', 'GPay'].map((p) => <span className="pay" key={p}>{p}</span>)}</div>
          </div>
          <div><h5>Shop</h5><Link to="/shop">All gifts</Link><Link to="/hamper-builder">Build a hamper</Link><Link to="/gift-finder">Gift finder</Link></div>
          <div><h5>Help</h5><Link to="/support">Help & support</Link><a href="/showcase.html">Showcase</a><Link to="/orders">Track order</Link></div>
          <div><h5>Account</h5><Link to="/account">My account</Link><Link to="/wishlist">Wishlist</Link><Link to="/cart">Cart</Link></div>
        </div>
      </div>

      <div className="toast" ref={toastRef} />
    </div>
  );
}

/* count-up animation (easeOutQuart), formats 50000->50k+, 4.9->4.9★, 99->99% */
function countUp(el) {
  const target = parseFloat(el.dataset.target), dur = 1700, t0 = performance.now();
  const fmt = (v) => {
    if (target === 4.9) return v.toFixed(1) + '★';
    if (target === 99) return Math.round(v) + '%';
    if (target >= 1000) return Math.round(v / 1000) + 'k+';
    return Math.round(v).toString();
  };
  (function step(now) {
    const p = Math.min((now - t0) / dur, 1), e = 1 - Math.pow(1 - p, 4);
    el.textContent = fmt(target * e);
    if (p < 1) requestAnimationFrame(step); else el.textContent = fmt(target);
  })(t0);
}
