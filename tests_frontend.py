import json, time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from microgridup import MGU_FOLDER

def run():
    options = Options()
    driver = webdriver.Chrome(options=options)

    driver.get('http://localhost:5000/')

    with open('testfiles/test_params.json') as file:
        test_params = json.load(file)
    crit_loads = test_params['crit_loads']
    MG_MINES = test_params['MG_MINES']
    algo_params = test_params['algo_params']
    pairings = algo_params['pairings']

    for _dir in MG_MINES:
        driver.find_element(By.XPATH, '//a[@href][text()="+"]').click()

        print(f'---------------------------------------------------------\nBeginning end-to-end test of {_dir}.\n---------------------------------------------------------')

        MODEL_DIR = driver.find_element(By.NAME, 'MODEL_DIR')
        MODEL_DIR.clear()
        MODEL_DIR.send_keys(f'{_dir}')

        driver.find_element(By.NAME, 'LOAD_CSV').send_keys(f'{MGU_FOLDER}/testfiles/lehigh_load.csv')

        if 'lehigh' in _dir:
            driver.find_element(By.ID, 'upload').click()

            driver.find_element(By.NAME, 'file').send_keys(f'{MGU_FOLDER}/testfiles/lehigh_base_3mg.dss')

            driver.find_element(By.ID, 'upload-file-btn').click()
        
        elif 'wizard' in _dir:
            driver.find_element(By.ID, 'wizard').click()

            # JavaScript shortcut.
            driver.execute_script('fillWizardLehigh()')

            # TO DO: Fill out circuit wizard with Selenium rather than using a JavaScript shortcut.
            # driver.find_element(By.XPATH, '//ul[@id="elements"]//li[@class="substation"]').click()
            # driver.find_element(By.XPATH, '//ul[@id="elements"]//input[@class="substation"]').send_keys(' sub')

            driver.find_element(By.ID, 'toDss').click()


        time.sleep(2)

        crit_loads = ['634a_data_center', '634b_radar', '634c_atc_tower', '675a_hospital', '675b_residential1', '675c_residential1', '645_hangar', '646_office']
        for load in crit_loads:
            checkbox = driver.find_element(By.XPATH, f'//label[text()="{load}"]')
            checkbox.click()
        
        algo = MG_MINES[_dir][1]
        select = Select(driver.find_element(By.ID, 'partitionMethod'))
        select.select_by_value(f'{MG_MINES[_dir][1]}')

        if algo in ('loadGrouping','manual'):
            driver.find_element(By.ID, 'mgQuantity').send_keys('3')
            driver.find_element(By.ID, 'makeDropdowns').click()
            # Fill out dropdowns.
            pairings.pop('None','')
            for key in pairings:
                for load in pairings[key]:
                    select = Select(driver.find_element(By.XPATH, f'//div[@id="dropDowns"]//label[text()=" {load}"]/select'))
                    select.select_by_value(key)
            if algo == 'manual':
                # Fill out switches and gen buses.
                switch = algo_params['switch']
                gen_bus = algo_params['gen_bus']
                for key in switch:
                    driver.find_element(By.ID, f'{key.lower()}Switch').send_keys(switch[key])
                    driver.find_element(By.ID, f'{key.lower()}Genbus').send_keys(gen_bus[key])
        elif algo in ('bottomUp','criticalLoads'):
            driver.find_element(By.ID, 'minQuantMgs').send_keys('3')
            driver.find_element(By.ID, 'previewPartitions').click()
        else:
            driver.find_element(By.ID, 'previewPartitions').click()

        time.sleep(2)

        technologies = ['fossil'] # 'solar' and 'battery' are checked by default when loading in data/static/lehigh_3mg_inputs.json.
        for tech in technologies:
            driver.find_element(By.NAME, f'{tech}').click()

        time.sleep(1)
        
        driver.find_element(By.ID, 'submitEverything').click()

        time.sleep(20)
    return

if __name__ == '__main__':
    run()