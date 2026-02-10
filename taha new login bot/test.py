from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_opts = Options()
chrome_opts.add_argument("--headless=new")
driver = webdriver.Chrome(options=chrome_opts)
driver.get("https://students.tahacollege.ca/studentportal/s/")
print("Title:", driver.title)
driver.quit()
