from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from django.http import JsonResponse


def get_phone_avito(driver,data):
    url = data.GET['url']
    print(url)
    #caps = DesiredCapabilities.PHANTOMJS
    #driver = webdriver.PhantomJS() #Remote("http://localhost:8001/wd/hub", desired_capabilities=caps)
    driver.get(url)
    # print("got url")
    driver.find_element_by_class_name("item-phone-button").click()
    # print("btn clicked")
    item = driver.find_element_by_css_selector(".item-phone-big-number img")
    # print(item)
    url = item.get_attribute("src")
    print(url)
    return JsonResponse({'url': url})


def get_phone_birge(data):
    url = data.GET['url']
    print(url)
    driver = webdriver.Remote("http://localhost:8001/wd/hub", desired_capabilities=DesiredCapabilities.PHANTOMJS)
    print("driver is made")
    driver.get(url)
    item = driver.find_element_by_class_name("dont_copy_phone")
    url = item.get_attribute("src")
    print(url)
    return JsonResponse({'url': url})


def get_phone_rabota(data):
    url = data.GET['url']
    print(url)
    driver = webdriver.Remote("http://localhost:8001/wd/hub", desired_capabilities=DesiredCapabilities.PHANTOMJS)
    print("driver is made")
    driver.get(url)
    driver.find_element_by_class_name("card-vacancy__xs-small").click()
    url = driver.find_element_by_css_selector(".h3 a[rel=nofollow]").get_attribute("href")
    #url = item.get_attribute("src")
    print(url)
    return JsonResponse({'tel': url})

def get_phone_jobmo(data):
    url = data.GET['url']
    print(url)
    caps = DesiredCapabilities.PHANTOMJS
    caps["phantomjs.page.setttings.loadImages"] = "true"
    driver = webdriver.Remote("http://localhost:8001/wd/hub", desired_capabilities=caps)
    print("driver is made")
    driver.get(url)
    print('got url')
    driver.find_element_by_css_selector("#p a").click()
    print('clicked')
    tel = driver.find_element_by_css_selector("#p a").get_attribute("innerHTML")
    print(url)
    return JsonResponse({'tel': tel})