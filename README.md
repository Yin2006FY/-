# 电商大数据分析与用户行为漏斗

## 项目简介
本项目模拟生成亿级电商用户行为数据（浏览→点击→下单→支付→复购），并基于该数据构建离线数仓与用户行为分析。数据完全由脚本生成，符合真实电商漏斗逻辑，可用于大数据平台技术验证、数据分析练习、面试项目展示

##一，模拟数据生成
  T1_2026-04-29.py文件
  - 用户数：20 万，商品数：5 万，支付订单数：50 万（含复购）
- 每个支付订单前置生成：浏览数 > 点击数 ≥ 1，时间严格递增
- 未转化行为（浏览/点击无下单）比例可调，模拟真实转化率
- 复购逻辑：基于历史支付时间，满足间隔天数后以一定概率生成新订单

前置前提--四个第三方包
pip install pandas
pip install numpy
pip install faker
pip install tqdm
  
输出文件products.csv 产品表,users.csv 用户信息表
        orders.csv 下单支付信息表, behaviors.csv 用户行为表
注意：用户行为表中order_id为null的即转化失败


##二，数据导入HDFS和HIVE数据仓库构建
  - ①，创建HDFS上的对应目录(/data已存在)
  - hadoop fs -mkdir /data/products /data/behaviors /data/users /data/orders
  -②，上传文件到对应HDFS目录,copyFromLocal=put
  - hadoop fs -copyFromLocal /tmp/orders.csv /data/orders
  - hadoop fs -copyFromLocal /tmp/users.csv /data/users
  - hadoop fs -copyFromLocal /tmp/behaviors.csv /data/behaviors
  - hadoop fs -copyFromLocal /tmp/products.csv /data/products
  - 注：文件位置根据自己的实际位置来
   - ③，hive映射表-(进入客户端操作)
  - su hive , hive
- create table behaviors
(user_id string,product_id string,behavior_type string,timestamp_str string,order_id string) 
row format delimited fields terminated by ',' stored as textfile location "/data/behaviors" TBLPROPERTIES ("skip.header.line.count" = "1");
  
- create table users
(user_id string,age int,gender string,city string,registera_date string) 
row format delimited fields terminated by ',' stored as TextFile location '/data/users' TBLPROPERTIES ("skip.header.line.count" = "1");
  
- create table orders
(order_id string,user_id string,product_id string,checkout_time_str string,pay_time_str string) 
row format delimited fields terminated by ',' stored as TextFile location '/data/orders' TBLPROPERTIES ("skip.header.line.count" = "1");
  
- create table products
(product_id string,category string,price double,brand string) 
row format delimited fields terminated by ',' stored as TextFile location '/data/products' TBLPROPERTIES ("skip.header.line.count" = "1");
 - :TBLPROPERTIES ("skip.header.line.count" = "1")-跳过首行（字段行）

 



