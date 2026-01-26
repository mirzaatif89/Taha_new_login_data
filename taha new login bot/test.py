from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
proxy = "http://wnwszvpt:79y9imzqi0qo@104.239.35.219:5901"  # same proxy, include scheme
opts = {"proxy": {"http": proxy, "https": proxy, "no_proxy": "localhost,127.0.0.1"}}
chrome_opts = Options(); chrome_opts.add_argument("--headless=new")
driver = webdriver.Chrome(options=chrome_opts, seleniumwire_options=opts)
driver.get("https://students.tahacollege.ca/studentportal/s/")
print("Title:", driver.title)
driver.quit()