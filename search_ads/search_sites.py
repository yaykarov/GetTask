from urllib.parse import quote
import re
from .models import HrSiteAdv, HrSiteReport, HrSiteAccount, get_digit_str
from .read_png import get_digits
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from pyquery import PyQuery as pq


def search_birge(keywords, accounts, maxpagenum, maxpos,report):
    url = 'https://moscow.birge.ru/catalog/rabota_predlagayu/filter/clear/apply/?'
    print("search in birge")
    print(keywords)
    ads = []
    status0 = "Поиск в Бирге "
    try:
        for keyword in keywords:
            key_url = url + "text=" + quote(keyword)
            position = 1
            for pagenum in range(0, maxpagenum):
                report.current_status = status0 + "по ключевому слову "+keyword+", страница "+str(pagenum)+" позиция "+str(position)+" "
                report.save()
                if pagenum==0:
                    r=pq(url=key_url)
                else:
                    r=pq(url=key_url+"&PAGEN_1="+str(pagenum+1))
                print("page: " + str(pagenum))
                refs = [link.attrib["href"] for link in r(".href-detail")]
                
                print("found refs: {}".format(len(refs)))
                for ref in refs:
                    try:
                        ref = "https://moscow.birge.ru"+ref
                        #print(ref)
                        item_r = pq(url=ref)
                        print(item_r(".name_ads").text())
                        report.current_status = status0 + "по ключевому слову " + keyword + ", страница " + str(pagenum)+" позиция "+str(position)+", \""+item_r(".name_ads").text()+"\""
                        report.save()
                        #print(driver.find_element_by_class_name("name_ads").get_attribute("innerText"))
                        if item_r(".dont_copy_phone") is None:
                            position += 1
                            continue
                        item_phone_url = item_r(".dont_copy_phone").attr("src")
                        item_phone = str(get_digits(fname="https://moscow.birge.ru"+item_phone_url,site="birge"))
                        print("position: {}".format(position))
                        for account in accounts:
                            print("{0} - {1}".format(item_phone, account.phone))
                            if item_phone == account.phone:
                                ad = HrSiteAdv()
                                ad.account = account
                                ad.keyword = keyword
                                ad.site = "Бирге"
                                ad.date_time_str = item_r(".city-date").text()
                                ad.ref = ref
                                print("got page " + ad.ref)
                                ad.title = item_r(".name_ads").text()
                                ad.position = position
                                ads.append(ad)
                                break
                        if position >= maxpos:
                            break
                    except Exception as exc:
                        print("error: {}".format(str(exc)))
                    position += 1
                if pagenum + 1 >= maxpagenum:
                     break
                if position >= maxpos:
                    break
    except ConnectionResetError:
        print("connection error")

    return ads


def search_avito(driver, keywords, accounts, maxpagenum, maxpos,report,in_vacancies=False):
    print("search in avito")
    if in_vacancies=='on':
        host_url = 'https://www.avito.ru/moskva/vakansii?s_trg=3&'
    else:
        host_url = 'https://www.avito.ru/moskva?s_trg=3&'
    ads = []
    status0 = "Поиск в Авито "
    try:
        for keyword in keywords:
            key_url = host_url + "q=" + quote(keyword, encoding='utf-8')
            print(key_url)
            position = 1
            driver.get(key_url)
            for pagenum in range(0, maxpagenum):
                report.current_status = status0 + "по ключевому слову "+keyword+", страница "+str(pagenum)+" позиция "+str(position)+" "
                report.save()
                print("page: " + str(pagenum))
                refs = [link.get_attribute("href") for link in driver.find_elements_by_class_name("item-description-title-link")]
                #print(refs)
                for ref in refs:
                    if position >= maxpos:
                        return ads
                    print("position: {}".format(position))
                    try:
                        print(ref)
                        driver.get(ref)
                        phone_tag = None #driver.find_element_by_css_selector(".js-item-phone-button")
                        phone_tag = WebDriverWait(driver,5).until(EC.element_to_be_clickable((By.CSS_SELECTOR,".js-item-phone .js-item-phone-button")))
                        phone_tag.click()
                        print("clicked")
                        phone_img_url=None
                        phone_img=WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.CSS_SELECTOR,".js-item-phone .js-item-phone-button img")))
                        print("item")
                        phone_img_url = phone_img.get_attribute("src")
                        item_phone = str(get_digits(phone_img_url))
                        report.current_status = status0 + "по ключевому слову "+keyword+", страница "+str(pagenum)+" позиция "+str(position)+", распознан номер "+item_phone
                        report.save()
                        print("recognized: '{}'".format(item_phone))
                        for account in accounts:
                            print("account phone: '{}'".format(account.phone))
                            if item_phone == account.phone:
                                report.current_status = status0 + "по ключевому слову " + keyword + ", страница " + str(
                                    pagenum)+" позиция "+str(position)+", найдено совпадание по "+str(account)
                                report.save()
                                ad = HrSiteAdv()
                                ad.account = account
                                ad.keyword = keyword
                                ad.date_time_str = driver.find_element_by_class_name("title-info-metadata-item").get_attribute("innerText")
                                ad.ref = ref
                                ad.site = "Авито"
                                print("got page "+ad.ref)
                                ad.title = driver.find_element_by_css_selector(".title-info-title-text").get_attribute("innerText")
                                ad.position = position
                                ads.append(ad)
                                break
                    except Exception as exc:
                        print("error: {}".format(str(exc)))
                    position += 1
                    if position >= maxpos:
                        break
                if pagenum+1 >= maxpagenum:
                    break
                if position >= maxpos:
                    break
                driver.back()
                try:
                    pag = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, ".js-pagination-next")))
                    #pag = driver.find_element_by_class_name("js-pagination-next")
                    if pag is None:
                        print("no next page")
                        break
                    else:
                        pag.click()
                except:
                    break
    except ConnectionResetError:
        print("connection error")

    return ads


def search_rabota(keywords, accounts, pagenum, maxpos,report):
    #print(keywords)
    #print(accounts)
    print("search in rabota")
    url = 'https://www.rabota.ru/vacancy/'
    results = []
    status0 = "Поиск в Работа "
    for keyword in keywords:
        print("keyword: " + keyword)
        key_url = url + quote(keyword)
        print("url: "+key_url)
        position = 1
        for i in range(0, pagenum):
            try:
                report.current_status = status0 + "по ключевому слову "+keyword+", страница "+str(i)+" позиция "+str(position)+" "
                report.save()
                if i == 0:
                    r = pq(url=key_url) #session.get(key_url)
                else:
                    r = pq(url=key_url + "?page=" + str(i + 1)) #session.get(key_url + "?page=" + str(i + 1))
                    print(key_url + "?page=" + str(i))
                items = r.find(".list-vacancies__item")
                print("Searching items " + str(len(items)))
                for item in items:
                    try:
                        pq_item=pq(item)
                        title_tag = pq_item.find(".list-vacancies__company-title")
                        if title_tag.attr('href') is None:
                            continue
                        item_url = 'https://www.rabota.ru' + title_tag.attr('href')
                        tel_href_item = pq_item.find(".show-box__content .h3 a[rel='nofollow']")
                        if tel_href_item is not None and len(tel_href_item) != 0:
                            tel_href = tel_href_item.attr('href')
                        else:
                            continue
                        item_tel = get_digit_str(tel_href)[1:] #re.search("[0-9]+", tel_href).group(0)
                        print(item_tel)
                        report.current_status = status0 + "по ключевому слову " + keyword + ", страница " + str(i)+" позиция "+str(position)+" по номеру " + str(item_tel)
                        report.save()
                        if item_tel == "":
                            continue
                        for account in accounts:
                            if account.phone == get_digit_str(item_tel):
                                ad = HrSiteAdv()
                                print("watching tel " + str(item_tel))
                                ad.account = account
                                ad.title = pq_item.find(".list-vacancies__company-title").attr('title')
                                ad.keyword = keyword
                                ad.site = "Работа"
                                ad.date_time_str = pq_item.find(".list-vacancies__date").text()
                                ad.ref = item_url
                                ad.position = position
                                results.append(ad)
                                break
                        if position >= maxpos:
                            break
                    except Exception as exc:
                        print("error: {}".format(str(exc)))
                    position += 1

            except Exception as exc:
                print("error: {}".format(str(exc)))
            position += 1
            if position >= maxpos:
                break
    print(results)
    return results


def search_jerdesh(keywords, accounts, pagenum, maxpos,report):
    print("search in jerdesh")
    url = 'http://jerdesh.ru/search'
    ads = []
    status0 = "Поиск в Жердеш "
    for keyword in keywords:
        keyword = re.sub(" +", "+", keyword)
        # tel = re.search("[0-9]+",tel).group(0)
        page_url = url + "/pattern," + quote(keyword,encoding='utf-8')
        position = 1
        for i in range(0, pagenum):
            try:
                report.current_status = status0 + "по ключевому слову "+keyword+", страница "+str(i)+" позиция "+str(position)+" "
                report.save()
                print("page: " + str(i))
                print(page_url)
                if i == 0:
                    r = pq(url=page_url) #session.get(url)
                else:
                    r = pq(url=page_url + "/iPage," + str(i + 1)) #session.get(page_url + "/iPage," + str(i + 1))
                items = r(".listing-card")
                print("items: " + str(len(items)))
                for item in items:
                    try:
                        pq_item=pq(item)
                        phone_item = pq_item.find(".protectedNumber")
                        if phone_item is None or len(phone_item) == 0:
                            continue
                        else:
                            position += 1
                        print("position: " + str(position))
                        item_tel = get_digit_str(phone_item.attr('title'))[1:]
                        print("tel: " + item_tel)
                        print("title: " + pq_item.find(".title").attr('title'))
                        report.current_status = status0 + "по ключевому слову " + keyword + ", страница " + str(pagenum)+" позиция "+str(position)+", \""+pq_item.find(".title").attr('title')+"\""
                        report.save()
                        for account in accounts:
                            if account.phone == get_digit_str(item_tel):
                                ad = HrSiteAdv()
                                print(item_tel)
                                title_item = pq_item.find(".title")
                                ad.title = title_item.attr('title')
                                ad.position = position
                                ad.account = account
                                ad.site = "Jerdesh"
                                ad.keyword = keyword
                                ad.ref = title_item.attr('href')
                                ad.date_time_str = pq_item.find(".listing-attributes").text()
                                ads.append(ad)
                                break

                        if position >= maxpos:
                            break
                    except Exception as exc:
                        print(exc)
                    position += 1
                    if position >= maxpos:
                        break
            except Exception as exc:
                position += 1
                print(exc)
            if position >= maxpos:
                break

    return ads


def search_jobmo(driver, keywords, accounts, maxpagenum, maxpos,report):
    print("search in jobmo")
    #print(accounts)
    ads = []
    url = 'https://www.job-mo.ru/search.php?r=vac&submit=1&'
    status0 = "Поиск в JobMo "
    try:
        for keyword in keywords:
            print(keyword)
            key_url = url + "srprofecy=" + quote(keyword, encoding="windows-1251")
            print(key_url)
            position = 1
            for pagenum in range(0, maxpagenum):
                if pagenum == 0:
                    driver.get(key_url)
                else:
                    driver.get(key_url+"&page="+str(pagenum+1))
                report.current_status = status0 + "по ключевому слову "+keyword+", страница "+str(pagenum)+" позиция "+str(position)+" "
                report.save()
                print("page: " + str(pagenum))
                refs = [link.get_attribute("href") for link in driver.find_elements_by_css_selector(".prof a")]
                print(refs)
                for ref in refs:
                    try:
                        print(ref)
                        print("position: {}".format(position))
                        driver.get(ref)
                        try:
                            WebDriverWait(driver,5).until(EC.visibility_of_element_located((By.ID,"p")))
                        except TimeoutException:
                            position += 1
                            continue
                        phone_tag = driver.find_element_by_css_selector("#p a")
                        phone_tag.click()
                        try:
                            item_phone = get_digit_str(driver.find_element_by_css_selector("#p a").get_attribute("innerText"))
                        except StaleElementReferenceException:
                            time.sleep(1)
                            item_phone = get_digit_str(
                                driver.find_element_by_css_selector("#p a").get_attribute("innerText"))
                        wn = 0
                        while item_phone == '' or wn >= 5:
                            time.sleep(0.5)
                            item_phone = get_digit_str(driver.find_element_by_css_selector("#p a").get_attribute("innerText"))
                        #print(phone_tag.get_attribute("class"))
                        print("phone: '{}'".format(item_phone))
                        print(keyword)
                        for account in accounts:
                            print("account phone: '{}'".format(account.phone))
                            report.save()
                            if account.phone in item_phone:
                                report.current_status = status0 + "по ключевому слову " + keyword + ", страница " + str(pagenum)+" позиция "+str(position)+", найдено совпадение по телефону менеджера "+account.name
                                ad = HrSiteAdv()
                                ad.account = account
                                ad.keyword = keyword
                                ad.date_time_str = driver.find_element_by_class_name("small").get_attribute("innerText")
                                ad.ref = ref
                                ad.site = "Job-mo"
                                print("got page "+ad.ref)
                                ad.title = driver.find_element_by_css_selector(".contentmain h1").get_attribute("innerText")
                                ad.position = position
                                ads.append(ad)
                                break
                    except Exception as exc:
                        print(exc)
                    position += 1
                    if position >= maxpos:
                        break
                if position >= maxpos:
                    break

    except ConnectionResetError:
        print("connection error")

    return ads
