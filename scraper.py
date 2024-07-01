from selenium import webdriver as wd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException as NSEE
import itertools
import pandas as pd
from tqdm import tqdm


def str_to_s(text: str) -> float:
    try:
        return 60 * int(text[:2]) + int(text[3:5]) + int(text[6:8]) / 100
    except ValueError:
        return None


def is_vw_or_heat(text: str) -> bool:
    return "voorwedstrijd" in text or "heat" in text.lower()


def get_prelims(context) -> list[str]:
    ass = context.find_elements(By.TAG_NAME, "a")
    return [a.get_attribute('href') for a in ass if is_vw_or_heat(a.text) and a.get_attribute('href') is not None]


def get_race_results(cur_driver, race):
    cur_driver.get(race)
    element_present = EC.presence_of_element_located((By.ID, 'container'))
    WebDriverWait(cur_driver, 5).until(element_present)
    race = cur_driver.find_element(By.ID, "container")
    time = race.find_element(By.TAG_NAME, "h2").text[3:8]
    results = [rc for rc in race.find_elements(By.CLASS_NAME, "timeteam") if has_th(rc)][0]
    df = pd.read_html(results.get_attribute("outerHTML"))[0]
    if "finishinterval" in df.columns:
        df = df.rename({"finishinterval": "finish"}, axis=1)
    if "lane" in df.columns:
        df = df.rename({"lane": "baan"}, axis=1)
    cols = ["baan", "finish"]
    df = df[cols].dropna()
    df['baan'] = df['baan'].map(lambda x: x[1])
    df['finish'] = df['finish'].map(str_to_s)
    df['time_of_race'] = time
    return df


def has_th(x):
    try:
        x.find_element(By.TAG_NAME, "th")
    except NSEE as e:
        return False
    else:
        return True


def get_event_results(link: str, venue: str) -> pd.DataFrame:
    driver = wd.Firefox()
    driver.get(link)
    regatta = driver.find_elements(By.ID, "container")[0]
    dates = [i.text for i in regatta.find_elements(By.TAG_NAME, "h4")]
    race_containers = [rc for rc in regatta.find_elements(By.CLASS_NAME, "timeteam") if has_th(rc)]
    race_links = [get_prelims(rc) for rc in race_containers]
    event_df = None
    for date, links in zip(dates, race_links):
        day_results = [get_race_results(driver, link) for link in links]
        if day_results!=[]:
            day_df = pd.concat(day_results, axis=0, ignore_index=True)
            day_df['date'] = date
            if event_df is None:
                event_df = day_df
            else:
                event_df = pd.concat([event_df, day_df], axis=0, ignore_index=True)
    event_df['venue'] = venue
    driver.quit()
    return event_df


def race_url(name, year):
    if year>2017:
        last = 'races'
    else:
        last = 'heats'
    return f"https://regatta.time-team.nl/{name}/{year}/results/{last}.php"


def get_valid_races(to_check):
    driver = wd.Firefox()
    checked = []
    for event in to_check:
        driver.get(race_url(event[0], event[1]))
        if "The selected regatta is not found." not in driver.find_element(By.TAG_NAME, 'body').text:
            container = driver.find_element(By.ID, "container")
            if len(container.text) > 4:
                checked.append((event[0], event[1]))
    driver.quit()
    return checked

def boba(x, bobalist):
    if x in bobalist:
        return "bosbaan"
    else:
        return "wab"

if __name__ == "__main__":
    races = ['arb', 'nwr', 'hollandbeker', 'westelijke', 'raceroei', 'hollandia', 'voorjaarsregatta']
    bosbaan = ['arb', 'hollandbeker', 'hollandia', 'voorjaarsregatta']
    years = [2024, 2023, 2022, 2021, 2020, 2019]
    valid_events = list(get_valid_races(itertools.product(races, years)))
    valid_events.remove(('westelijke',2020))
    valid_events.remove(('hollandia',2021))
    bosbaan_collection = []
    wab_collection = []
    collection = []

    # df = get_event_results(race_url('hollandia',2019), 'wab')

    for valid_event in tqdm(valid_events):
        event_df = get_event_results(race_url(valid_event[0], valid_event[1]), boba(valid_event[0], bosbaan))
        event_df['event_name'] = valid_event[0]
        if boba(valid_event[0], bosbaan) == "bosbaan":
            bosbaan_collection.append(event_df)
        else:
            wab_collection.append(event_df)
        collection.append(event_df)
        event_df.to_csv(f"wedstrijden/{valid_event[0]}_{valid_event[1]}.csv")
    bosbaan_df = pd.concat(bosbaan_collection, axis=0, ignore_index=True)
    bosbaan_df.to_csv("wedstrijden/bosbaan.csv")
    wab_df = pd.concat(wab_collection, axis=0, ignore_index=True)
    wab_df.to_csv("wedstrijden/wab.csv")
    collection_df = pd.concat(collection, axis=0, ignore_index=True)
    collection_df.to_csv("wedstrijden/alles.csv")
