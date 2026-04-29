import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
from tqdm import tqdm
from faker import Faker

fake = Faker('zh_CN')
random.seed(42)
np.random.seed(42)

# ========== 配置 ==========
NUM_PAYMENTS = 50_000
NUM_USERS = 20_000
NUM_PRODUCTS = 5_000
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2023, 12, 31)
REPURCHASE_INTERVAL_DAYS = 30
REPURCHASE_PROB = 0.35

MIN_VIEWS = 2
MAX_VIEWS = 8
MIN_CLICKS = 1

NON_CONVERSION_RATIO = 3
MIN_CHECKOUT_TO_PAY_MIN = 1
MAX_CHECKOUT_TO_PAY_MIN = 180

# 用户活跃度权重
USER_ACTIVITY_WEIGHTS = np.random.power(2.0, NUM_USERS)
USER_ACTIVITY_WEIGHTS /= USER_ACTIVITY_WEIGHTS.sum()

# 商品热度权重
PRODUCT_POPULARITY = np.random.power(1.5, NUM_PRODUCTS)
PRODUCT_POPULARITY /= PRODUCT_POPULARITY.sum()

# ---------- 预计算日期权重 ----------
date_list = pd.date_range(START_DATE, END_DATE, freq='D')
date_list_py = [d.to_pydatetime() for d in date_list]
day_weights = []
for d in date_list_py:
    w = 1.0
    if d.weekday() >= 5:
        w *= 1.3
    if (d.month == 9 and d.day >= 25) or (d.month == 10 and d.day <= 10):
        w *= 1.5
    if (d.month == 1 and d.day >= 15) or (d.month == 2 and d.day <= 10):
        w *= 1.2
    day_weights.append(w)
day_weights = np.array(day_weights)
day_weights /= day_weights.sum()


def random_timestamp_by_weight():
    chosen_date = np.random.choice(date_list_py, p=day_weights)
    end_dt = chosen_date + timedelta(days=1) - timedelta(seconds=1)
    return fake.date_time_between(start_date=chosen_date, end_date=end_dt)


# ========== 1. 生成基础表 ==========
print("生成用户表...")
users = []
for i in range(NUM_USERS):
    users.append({
        'user_id': f"U{i + 1:08d}",
        'age': random.randint(18, 70),
        'gender': random.choice(['M', 'F']),
        'city': fake.city(),
        'register_date': fake.date_between(start_date=START_DATE - timedelta(days=365), end_date=START_DATE)
    })
df_users = pd.DataFrame(users)
df_users.to_csv('users.csv', index=False, encoding='utf-8-sig')

print("生成商品表...")
categories = ['Electronics', 'Clothing', 'Home', 'Food', 'Beauty', 'Sports', 'Books', 'Toys']
products = []
for i in range(NUM_PRODUCTS):
    cat = random.choice(categories)
    price = round(random.uniform(10, 2000), 2)
    products.append({
        'product_id': f"P{i + 1:08d}",
        'category': cat,
        'price': price,
        'brand': fake.company()
    })
df_products = pd.DataFrame(products)
df_products.to_csv('products.csv', index=False, encoding='utf-8-sig')

# ========== 2. 生成支付订单（首购 + 复购）==========
print("分配支付订单数到用户...")
user_ids = df_users['user_id'].values
base_counts = np.random.negative_binomial(2, 0.3, NUM_USERS) + 1
weighted_counts = base_counts * USER_ACTIVITY_WEIGHTS
order_counts = (weighted_counts / weighted_counts.sum() * NUM_PAYMENTS).astype(int)
diff = NUM_PAYMENTS - order_counts.sum()
if diff > 0:
    idx_sorted = np.argsort(USER_ACTIVITY_WEIGHTS)[::-1]
    for i in range(diff):
        order_counts[idx_sorted[i % len(idx_sorted)]] += 1
elif diff < 0:
    idx_sorted = np.argsort(USER_ACTIVITY_WEIGHTS)
    for i in range(-diff):
        if order_counts[idx_sorted[i]] > 1:
            order_counts[idx_sorted[i]] -= 1

payment_orders = []
order_id_counter = 1
last_pay = {}

print("生成首购订单...")
for user_idx, user_id in enumerate(user_ids):
    n = order_counts[user_idx]
    for _ in range(n):
        product_id = np.random.choice(df_products['product_id'], p=PRODUCT_POPULARITY)
        pay_time = random_timestamp_by_weight()
        offset = random.randint(MIN_CHECKOUT_TO_PAY_MIN, MAX_CHECKOUT_TO_PAY_MIN)
        checkout_time = pay_time - timedelta(minutes=offset)
        if checkout_time < START_DATE:
            checkout_time = START_DATE
            pay_time = checkout_time + timedelta(minutes=offset)
        order_id = f"ORD{order_id_counter:010d}"
        order_id_counter += 1
        payment_orders.append({
            'order_id': order_id,
            'user_id': user_id,
            'product_id': product_id,
            'checkout_time': checkout_time,
            'pay_time': pay_time
        })
        last_pay[(user_id, product_id)] = pay_time

print("生成复购订单...")
for _round in range(3):
    new_orders = []
    items = list(last_pay.items())
    for (user_id, product_id), last_pt in items:
        earliest_next = last_pt + timedelta(days=REPURCHASE_INTERVAL_DAYS)
        if earliest_next > END_DATE:
            continue
        if random.random() > REPURCHASE_PROB:
            continue
        pay_time = random_timestamp_by_weight()
        if pay_time < earliest_next:
            pay_time = earliest_next + timedelta(minutes=random.randint(1, 60 * 24))
        if pay_time > END_DATE:
            continue
        offset = random.randint(MIN_CHECKOUT_TO_PAY_MIN, MAX_CHECKOUT_TO_PAY_MIN)
        checkout_time = pay_time - timedelta(minutes=offset)
        if checkout_time < earliest_next:
            checkout_time = earliest_next
            pay_time = checkout_time + timedelta(minutes=offset)
        if pay_time > END_DATE:
            continue
        order_id = f"ORD{order_id_counter:010d}"
        order_id_counter += 1
        new_orders.append({
            'order_id': order_id,
            'user_id': user_id,
            'product_id': product_id,
            'checkout_time': checkout_time,
            'pay_time': pay_time
        })
        last_pay[(user_id, product_id)] = pay_time
    if not new_orders:
        break
    payment_orders.extend(new_orders)

print(f"总支付订单数: {len(payment_orders)}")
payment_orders.sort(key=lambda x: x['pay_time'])

# ========== 3. 为每个支付订单生成前置浏览和点击 ==========
print("生成订单行为链...")
all_behaviors = []

for order in tqdm(payment_orders, desc="行为链"):
    uid = order['user_id']
    pid = order['product_id']
    checkout_time = order['checkout_time']
    pay_time = order['pay_time']
    oid = order['order_id']

    V = random.randint(MIN_VIEWS, MAX_VIEWS)
    C = random.randint(MIN_CLICKS, V - 1)

    latest_click = checkout_time - timedelta(minutes=1)
    earliest_click = max(START_DATE, checkout_time - timedelta(hours=48))
    if earliest_click >= latest_click:
        earliest_click = latest_click - timedelta(minutes=10)
    click_times = sorted([fake.date_time_between(start_date=earliest_click, end_date=latest_click) for _ in range(C)])

    if C > 0:
        max_view = click_times[0] - timedelta(seconds=1)
    else:
        max_view = checkout_time - timedelta(seconds=1)
    earliest_view = max(START_DATE, checkout_time - timedelta(days=7))
    if earliest_view >= max_view:
        earliest_view = max_view - timedelta(days=1)
    view_times = sorted([fake.date_time_between(start_date=earliest_view, end_date=max_view) for _ in range(V)])

    for vt in view_times:
        all_behaviors.append(
            {'user_id': uid, 'product_id': pid, 'behavior_type': 'view', 'timestamp': vt, 'order_id': oid})
    for ct in click_times:
        all_behaviors.append(
            {'user_id': uid, 'product_id': pid, 'behavior_type': 'click', 'timestamp': ct, 'order_id': oid})
    all_behaviors.append(
        {'user_id': uid, 'product_id': pid, 'behavior_type': 'checkout', 'timestamp': checkout_time, 'order_id': oid})
    all_behaviors.append(
        {'user_id': uid, 'product_id': pid, 'behavior_type': 'purchase', 'timestamp': pay_time, 'order_id': oid})

# ========== 4. 生成未转化的浏览/点击 ==========
converted_views = sum(1 for b in all_behaviors if b['behavior_type'] == 'view')
converted_clicks = sum(1 for b in all_behaviors if b['behavior_type'] == 'click')
target_non_views = int(converted_views * NON_CONVERSION_RATIO)
target_non_clicks = int(converted_clicks * NON_CONVERSION_RATIO)

print(f"生成未转化行为: 浏览 {target_non_views}, 点击 {target_non_clicks}")


def random_non_conversion_behavior(behavior_type):
    uid = np.random.choice(user_ids, p=USER_ACTIVITY_WEIGHTS)
    pid = np.random.choice(df_products['product_id'], p=PRODUCT_POPULARITY)
    ts = random_timestamp_by_weight()
    return {
        'user_id': uid,
        'product_id': pid,
        'behavior_type': behavior_type,
        'timestamp': ts,
        'order_id': None
    }


non_behaviors = []
for _ in tqdm(range(target_non_views), desc="未转化浏览"):
    non_behaviors.append(random_non_conversion_behavior('view'))
for _ in tqdm(range(target_non_clicks), desc="未转化点击"):
    non_behaviors.append(random_non_conversion_behavior('click'))

all_behaviors.extend(non_behaviors)
random.shuffle(all_behaviors)

# ========== 5. 保存CSV ==========
print("保存数据...")
df_behaviors = pd.DataFrame(all_behaviors)
df_behaviors['timestamp_str'] = df_behaviors['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
df_behaviors.drop(columns='timestamp', inplace=True)
df_behaviors.to_csv('behaviors.csv', index=False, encoding='utf-8-sig',
                    columns=['user_id', 'product_id', 'behavior_type', 'timestamp_str', 'order_id'])

df_orders = pd.DataFrame(payment_orders)
df_orders['checkout_time_str'] = df_orders['checkout_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
df_orders['pay_time_str'] = df_orders['pay_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
df_orders.drop(columns=['checkout_time', 'pay_time'], inplace=True)
df_orders.to_csv('orders.csv', index=False, encoding='utf-8-sig',
                 columns=['order_id', 'user_id', 'product_id', 'checkout_time_str', 'pay_time_str'])

print("数据生成完成！")