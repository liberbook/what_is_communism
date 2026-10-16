#!/usr/bin/env python3
"""Build italiano/glossary.ru-it.json, the Russian -> Italian translation glossary.

The curated entries below merge the terms fixed while comparing translations of
chapter 03 with the candidates harvested from every chapter. For each entry the
Russian text is scanned for inflected occurrences of the source term (case
forms, plurals, adjective agreement) and every surface form found is added as a
'|' alternative, because TranslateBooksWithLLMs' per-chunk glossary filter
matches source terms literally (case-sensitive, word boundaries).

By default the Russian text is read from russian/parts/*.tex (converted to
plain text with parts_text_exchange.py, with the PDF-extraction artefacts
fixed: "word- word" hyphen breaks joined, Roman numerals typed with Cyrillic
letters made Latin). --corpus points to a directory of exported .txt parts
instead.

Usage: python3 build_glossary.py [--corpus DIR] [--out italiano/glossary.ru-it.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# (source, target, category, note)
ENTRIES: list[tuple[str, str, str, str]] = [
    # --- book, authors, section titles (keep the TOC stable) ---
    ("Что такое коммунизм?", "Che cos'è il comunismo?", "title", "book title"),
    ("Группа Энгельс", "Gruppo Engels", "organization", "author collective"),
    ("Изобретаем «очки-велосипед»", "Inventiamo gli «occhiali-bicicletta»", "title", "section 01"),
    ("Предисловие", "Prefazione", "title", "section 02"),
    ("Основание коммунизма", "Il fondamento del comunismo", "title", "section 03"),
    ("Коммунизм как реальность в общественном производстве", "Il comunismo come realtà nella produzione sociale", "title", "section 04"),
    ("Общая (общественная) собственность", "La proprietà comune (sociale)", "title", "section 05"),
    ("Необходимый труд и условия для коммунистической деятельности", "Il lavoro necessario e le condizioni per l'attività comunista", "title", "section 06"),
    ("Коммунизм и управление общественной жизнью", "Il comunismo e la gestione della vita sociale", "title", "section 07"),
    ("Коммунизм и личность", "Il comunismo e la personalità", "title", "section 08"),
    ("Коммунизм и семья", "Il comunismo e la famiglia", "title", "section 09"),
    ("Коммунизм и общественное сознание", "Il comunismo e la coscienza sociale", "title", "section 10"),
    ("Заключение", "Conclusione", "title", "section 11"),

    # --- persons (scientific transliteration as on Italian Wikipedia) ---
    ("Маркс", "Marx", "person", ""),
    ("Энгельс", "Engels", "person", ""),
    ("Фридрих Энгельс", "Friedrich Engels", "person", ""),
    ("Ленин", "Lenin", "person", ""),
    ("Фейербах", "Feuerbach", "person", ""),
    ("Бенедикт Спиноза", "Baruch Spinoza", "person", ""),
    ("Гегель", "Hegel", "person", ""),
    ("Григорий Горин", "Grigorij Gorin", "person", "screenwriter"),
    ("Мюнхгаузен", "Münchhausen", "person", ""),
    ("Маяковский", "Majakovskij", "person", ""),
    ("Константин Сёмин", "Konstantin Sëmin", "person", ""),
    ("Евгений Спицин", "Evgenij Spicyn", "person", "the source misspells Спицын; use the correct name"),
    ("Спицин", "Spicyn", "person", ""),
    ("Никита Михалков", "Nikita Michalkov", "person", ""),
    ("Михалков", "Michalkov", "person", ""),
    ("Глушков", "Gluškov", "person", "Viktor Michajlovič Gluškov, OGAS project"),
    ("Макаренко", "Makarenko", "person", "Anton Semënovič Makarenko"),
    ("Антон Семенович", "Anton Semënovič", "person", ""),
    ("Горький", "Gor'kij", "person", ""),
    ("Дзержинский", "Dzeržinskij", "person", ""),
    ("Прудон", "Proudhon", "person", ""),
    ("Фурье", "Fourier", "person", ""),
    ("Сен-Симон", "Saint-Simon", "person", ""),
    ("Оуэн", "Owen", "person", ""),
    ("Бакунин", "Bakunin", "person", ""),
    ("Арнольд Руге", "Arnold Ruge", "person", ""),
    ("Александра Коллонтай", "Aleksandra Kollontaj", "person", ""),
    ("Коллонтай", "Kollontaj", "person", ""),
    ("Илья Эренбург", "Il'ja Ėrenburg", "person", ""),
    ("Вася", "Vasja", "person", "everyman name, keep transliterated"),
    ("Петя", "Petja", "person", "everyman name, keep transliterated"),

    # --- titles of works (established Italian titles) ---
    ("Тот самый Мюнхгаузен", "Quel Münchhausen", "title", "1979 TV film"),
    ("Последний звонок", "L'ultima campanella", "title", "documentary"),
    ("Цитадель", "La cittadella", "title", "Michalkov's film"),
    ("Критика Готской программы", "Critica del programma di Gotha", "title", ""),
    ("Готская программа", "programma di Gotha", "title", ""),
    ("Великий почин", "La grande iniziativa", "title", "Lenin 1919"),
    ("Эльберфельдские речи", "Discorsi di Elberfeld", "title", "Engels 1845"),
    ("Государство и революция", "Stato e rivoluzione", "title", "Lenin"),
    ("Манифест коммунистической партии", "Manifesto del Partito Comunista", "title", ""),
    ("Манифест", "Manifesto", "title", "short form of the Manifesto"),
    ("Экономическо-философские рукописи 1844 года", "Manoscritti economico-filosofici del 1844", "title", ""),
    ("Рукописи", "Manoscritti", "title", "short form"),
    ("Экономические рукописи 1857–1859 годов", "Manoscritti economici del 1857-1859", "title", "the Grundrisse"),
    ("Капитал", "Il Capitale", "title", "as a title"),
    ("Происхождение семьи, частной собственности и государства", "L'origine della famiglia, della proprietà privata e dello Stato", "title", "Engels"),
    ("Дорогу крылатому Эросу!", "Largo all'Eros alato!", "title", "Kollontaj 1923"),
    ("Василиса Малыгина", "Vasilisa Malygina", "title", "Kollontaj"),
    ("Большая любовь", "Un grande amore", "title", "Kollontaj"),
    ("День второй", "Il secondo giorno", "title", "Ėrenburg 1933"),
    ("Что делать?", "Che fare?", "title", "Lenin"),
    ("Раб. Дело", "Rab. Delo", "title", "journal abbreviation inside a Lenin quote"),
    ("К критике гегелевской философии права", "Per la critica della filosofia del diritto di Hegel", "title", "Marx"),
    ("тезисы о Фейербахе", "Tesi su Feuerbach", "title", ""),

    # --- organizations, places, events, acronyms ---
    ("СССР", "URSS", "acronym", ""),
    ("Советский Союз", "Unione Sovietica", "place", ""),
    ("РФ", "Federazione Russa", "acronym", ""),
    ("США", "Stati Uniti", "acronym", ""),
    ("МОТ", "OIL", "acronym", "Organizzazione Internazionale del Lavoro"),
    ("ПО", "software", "acronym", "программное обеспечение"),
    ("нэп", "NEP", "acronym", ""),
    ("ликбез", "likbez", "acronym", "campagna di liquidazione dell'analfabetismo; the text glosses it"),
    ("всеобуч", "vseobuč", "acronym", "istruzione elementare universale; the text glosses it"),
    ("соцлагерь", "campo socialista", "organization", ""),
    ("большевики", "bolscevichi", "organization", ""),
    ("советы", "soviet", "organization", "invariable, lowercase: i soviet"),
    ("Советы рабочих, солдатских и крестьянских депутатов", "soviet dei deputati operai, soldati e contadini", "organization", ""),
    ("Всемирная республика Советов", "Repubblica mondiale dei soviet", "organization", ""),
    ("Временное правительство", "Governo provvisorio", "organization", ""),
    ("царское правительство", "governo zarista", "organization", ""),
    ("Интернационал", "Internazionale", "organization", ""),
    ("Парижская Коммуна", "Comune di Parigi", "event", "feminine"),
    ("Государственный комитет статистики", "Comitato statale di statistica", "organization", ""),
    ("Институт демографии НАН Украины", "Istituto di demografia dell'Accademia nazionale delle scienze dell'Ucraina", "organization", ""),
    ("колония имени Горького", "colonia Gor'kij", "organization", "Makarenko"),
    ("коммуна имени Дзержинского", "comune Dzeržinskij", "organization", "Makarenko"),
    ("физиократы", "fisiocratici", "organization", ""),
    ("тред-юнионы", "trade unions", "organization", ""),
    ("революционные интернационалисты", "internazionalisti rivoluzionari", "organization", ""),
    ("Макдональдс", "McDonald's", "organization", ""),
    ("Linux", "Linux", "organization", ""),
    ("Windows", "Windows", "organization", ""),
    ("Москва", "Mosca", "place", ""),
    ("Куба", "Cuba", "place", ""),
    ("Дрезден", "Dresda", "place", ""),
    ("Донбасс", "Donbass", "place", ""),
    ("Приднестровье", "Transnistria", "place", ""),
    ("Абхазия", "Abcasia", "place", ""),
    ("Южная Осетия", "Ossezia del Sud", "place", ""),
    ("Нагорный Карабах", "Nagorno Karabakh", "place", ""),
    ("Таджикистан", "Tagikistan", "place", ""),
    ("нацистская Германия", "Germania nazista", "place", ""),
    ("среднеазиатские республики", "repubbliche centroasiatiche", "place", ""),
    ("Московско-Казанская железная дорога", "ferrovia Mosca-Kazan'", "place", ""),
    ("Октябрь", "Ottobre", "event", "the October Revolution; centenario dell'Ottobre"),
    ("Великая Октябрьская Революция", "Grande Rivoluzione d'Ottobre", "event", ""),
    ("Великая Октябрьская социалистическая революция", "Grande Rivoluzione socialista d'Ottobre", "event", ""),
    ("Февральская революция", "Rivoluzione di febbraio", "event", ""),
    ("июльские события 1917 года", "giornate di luglio del 1917", "event", ""),
    ("двоевластие", "dualismo del potere", "concept", "Lenin's term"),
    ("Мировая Революция", "Rivoluzione mondiale", "event", "capitalized as the name of the hypothesis"),
    ("военный коммунизм", "comunismo di guerra", "event", ""),
    ("индустриализация", "industrializzazione", "event", ""),
    ("гражданская война", "guerra civile", "event", "the Russian Civil War"),
    ("Первая Мировая", "prima guerra mondiale", "event", ""),
    ("Великая Отечественная война", "Grande guerra patriottica", "event", ""),
    ("чеченские войны", "guerre cecene", "event", ""),
    ("коммунистический субботник", "sabato comunista", "event", "plural: sabati comunisti, as in the Italian Lenin"),
    ("субботник", "sabato comunista", "event", ""),
    ("Средние века", "Medioevo", "event", ""),
    ("распад СССР", "dissoluzione dell'URSS", "event", ""),
    ("реставрация капитализма", "restaurazione del capitalismo", "concept", ""),
    ("молочная кухня", "centro di distribuzione del latte per l'infanzia", "organization", "Soviet municipal service"),
    ("коммуна-общежитие", "casa-comune", "concept", "1920s house-communes"),
    ("сын полка", "figlio del reggimento", "phrase", "war orphans adopted by army units"),
    ("беспризорность", "infanzia abbandonata", "concept", ""),

    # --- author's coinages and core concepts of the essay ---
    ("очки-велосипед", "occhiali-bicicletta", "concept", "author's coinage after Majakovskij; keep the quotation marks"),
    ("непосредственно-коллективная форма", "forma immediatamente collettiva", "concept", ""),
    ("непосредственная коллективность", "collettività immediata", "concept", ""),
    ("формы коллективности", "forme di collettività", "concept", ""),
    ("непосредственно-общественный", "immediatamente sociale", "concept", ""),
    ("свободная деятельность", "attività libera", "concept", ""),
    ("коммунистическая деятельность", "attività comunista", "concept", ""),
    ("ростки коммунизма", "germogli del comunismo", "concept", "Lenin's image"),
    ("зародыш", "germe", "concept", "distinct from ростки (germogli) and клеточка (cellula)"),
    ("клеточка", "cellula", "concept", "Marx's cell-form"),
    ("хозяйственная ячейка", "unità economica", "concept", "not cellula"),
    ("товарное производство", "produzione di merci", "concept", ""),
    ("товар", "merce", "concept", ""),
    ("товарная форма", "forma di merce", "concept", ""),
    ("товаровладелец", "possessore di merci", "concept", ""),
    ("товаропроизводитель", "produttore di merci", "concept", ""),
    ("вещное производство", "produzione cosale", "concept", "вещный = cosale (sachlich), not reificato"),
    ("вещный характер труда", "carattere cosale del lavoro", "concept", ""),
    ("вещный труд", "lavoro cosale", "concept", ""),
    ("самостоятельно-вещная форма", "forma cosale autonoma", "concept", ""),
    ("способ производства", "modo di produzione", "concept", ""),
    ("коммунистический способ производства", "modo di produzione comunista", "concept", ""),
    ("производственные отношения", "rapporti di produzione", "concept", ""),
    ("общественные отношения", "rapporti sociali", "concept", ""),
    ("производительные силы", "forze produttive", "concept", ""),
    ("непосредственная производительная сила", "forza produttiva immediata", "concept", "science as a productive force"),
    ("средства производства", "mezzi di produzione", "concept", ""),
    ("предмет труда", "oggetto di lavoro", "concept", ""),
    ("общественный уклад", "assetto sociale", "concept", ""),
    ("общественное устройство", "ordinamento sociale", "concept", ""),
    ("общественный строй", "regime sociale", "concept", ""),
    ("общественное богатство", "ricchezza sociale", "concept", ""),
    ("общественное бытие", "essere sociale", "concept", ""),
    ("общественное бытие определяет общественное сознание", "l'essere sociale determina la coscienza sociale", "quote", "Marx 1859"),
    ("общественное сознание", "coscienza sociale", "concept", ""),
    ("формы общественного сознания", "forme della coscienza sociale", "concept", ""),
    ("классовое сознание", "coscienza di classe", "concept", ""),
    ("индивидуальное сознание", "coscienza individuale", "concept", ""),
    ("мифологическое сознание", "coscienza mitologica", "concept", ""),
    ("материалистическое понимание истории", "concezione materialistica della storia", "concept", ""),
    ("содержательная форма", "forma contenutistica", "concept", ""),
    ("универсальное отношение", "rapporto universale", "concept", ""),
    ("самоценная деятельность", "attività che ha valore in sé", "concept", ""),
    ("самоценность деятельности", "valore in sé dell'attività", "concept", ""),
    ("предметная деятельность", "attività oggettiva", "concept", "Tesi su Feuerbach"),
    ("предметно-практическое существо", "essere oggettivo-pratico", "concept", ""),
    ("созерцание", "intuizione", "concept", "Anschauung in the Tesi su Feuerbach"),
    ("практика", "prassi", "concept", ""),
    ("товарищество", "sodalizio", "concept", "not cameratismo (fascist connotation)"),
    ("свободная ассоциация", "libera associazione", "concept", ""),
    ("свободная и равная ассоциация производителей", "libera ed eguale associazione dei produttori", "quote", "Engels"),
    ("самодействующая и самоуправляемая ассоциация", "associazione autoattiva e autogovernata", "concept", ""),
    ("социальное творчество", "creatività sociale", "concept", ""),
    ("самодетерминация", "autodeterminazione", "concept", ""),
    ("самовозрастание", "autovalorizzazione", "concept", "Selbstverwertung des Werts"),
    ("освоение", "appropriazione", "concept", "appropriazione (della cultura, del mondo)"),
    ("присвоение", "appropriazione", "concept", "Aneignung"),
    ("частный характер присвоения", "carattere privato dell'appropriazione", "concept", ""),
    ("общественный характер присвоения", "carattere sociale dell'appropriazione", "concept", ""),
    ("по меркам истины, добра и красоты", "secondo i criteri della verità, del bene e della bellezza", "phrase", ""),
    ("по меркам свободы", "secondo la misura della libertà", "phrase", ""),
    ("на острие противоречий", "sul filo delle contraddizioni", "phrase", ""),
    ("целенаправленно", "in modo mirato", "phrase", ""),
    ("разбазаривание", "dilapidazione", "concept", ""),
    ("материалистические друзья гегелевской диалектики", "amici materialisti della dialettica hegeliana", "quote", "Lenin"),
    ("первейшая жизненная потребность", "primo bisogno della vita", "quote", "Critica del programma di Gotha"),
    ("первой потребностью жизни", "primo bisogno della vita", "quote", "same formula, chapter 02"),
    ("без нормы и вознаграждения", "senza norma e senza compenso", "quote", "Lenin, La grande iniziativa"),
    ("управление вещами", "amministrazione delle cose", "quote", "Engels"),
    ("управление людьми", "governo degli uomini", "quote", "Engels"),
    ("управление общественной жизнью", "gestione della vita sociale", "concept", ""),
    ("управление общественным развитием", "gestione dello sviluppo sociale", "concept", ""),
    ("управлять государством", "governare lo Stato", "phrase", "Lenin"),
    ("осознанная необходимость", "necessità compresa", "quote", "Engels/Hegel formula"),
    ("Каждый по способностям, каждому по потребностям", "Ognuno secondo le sue capacità, a ognuno secondo i suoi bisogni", "quote", "Critica del programma di Gotha"),
    ("высшая фаза коммунизма", "fase superiore del comunismo", "concept", ""),
    ("низшая фаза коммунизма", "prima fase del comunismo", "concept", ""),
    ("первая фаза коммунистического общества", "prima fase della società comunista", "concept", ""),
    ("переходный период", "periodo di transizione", "concept", ""),
    ("разделение труда", "divisione del lavoro", "concept", ""),
    ("общественное разделение труда", "divisione sociale del lavoro", "concept", ""),
    ("снятие разделения труда", "superamento della divisione del lavoro", "concept", ""),
    ("снятие", "superamento", "concept", "Aufhebung"),
    ("упразднение", "soppressione", "concept", "Bobbio's Manoscritti"),
    ("уничтожение частной собственности", "abolizione della proprietà privata", "concept", "Manifesto"),
    ("положительное упразднение частной собственности", "soppressione positiva della proprietà privata", "quote", "Manoscritti 1844"),
    ("противоположность умственного и физического труда", "antitesi tra lavoro intellettuale e lavoro fisico", "concept", ""),
    ("буржуазное право", "diritto borghese", "concept", ""),
    ("всестороннее развитие", "sviluppo onnilaterale", "concept", ""),
    ("универсально-развитая личность", "personalità universalmente sviluppata", "concept", ""),
    ("универсальный творец", "creatore universale", "concept", ""),
    ("личность", "personalità", "concept", "never persona"),
    ("личность-творец", "personalità creatrice", "concept", ""),
    ("дурная индивидуальность", "cattiva individualità", "concept", "Hegelian schlecht"),
    ("истинная индивидуальность", "vera individualità", "concept", ""),
    ("становление сущности человека", "divenire dell'essenza umana", "concept", ""),
    ("становление", "divenire", "concept", "Hegelian Werden"),
    ("становящийся человек", "uomo in divenire", "concept", ""),
    ("человеческая сущность", "essenza umana", "concept", ""),
    ("целостный человек", "uomo integrale", "concept", ""),
    ("общественный человек", "uomo sociale", "concept", ""),
    ("новый человек", "uomo nuovo", "concept", ""),
    ("минимум человечности", "minimo di umanità", "concept", ""),
    ("частная собственность", "proprietà privata", "concept", ""),
    ("личная собственность", "proprietà personale", "concept", "never proprietà individuale"),
    ("общая собственность", "proprietà comune", "concept", ""),
    ("общественная собственность", "proprietà sociale", "concept", ""),
    ("семейная собственность", "proprietà familiare", "concept", ""),
    ("земельная собственность", "proprietà fondiaria", "concept", ""),
    ("земельная рента", "rendita fondiaria", "concept", ""),
    ("частный собственник", "proprietario privato", "concept", ""),
    ("всеобщая частная собственность", "proprietà privata universale", "concept", "Manoscritti 1844"),
    ("грубый коммунизм", "comunismo rozzo", "concept", "Manoscritti 1844"),
    ("общность жён", "comunanza delle donne", "concept", ""),
    ("псевдокоммунизм", "pseudocomunismo", "concept", ""),
    ("обобществление нищеты", "socializzazione della miseria", "phrase", ""),
    ("Всё отнять и поделить", "Prendere tutto e spartire", "phrase", "Bulgakov allusion; keep the guillemets"),
    ("обобществление", "socializzazione", "concept", "not collettivizzazione"),
    ("формальное обобществление", "socializzazione formale", "concept", ""),
    ("реальное обобществление", "socializzazione reale", "concept", ""),
    ("рабочая сила", "forza-lavoro", "concept", "hyphenated"),
    ("купля-продажа рабочей силы", "compravendita della forza-lavoro", "concept", ""),
    ("наёмный труд", "lavoro salariato", "concept", ""),
    ("живой труд", "lavoro vivo", "concept", ""),
    ("необходимый труд", "lavoro necessario", "concept", ""),
    ("прибавочный труд", "pluslavoro", "concept", ""),
    ("прибавочный продукт", "plusprodotto", "concept", ""),
    ("прибавочная стоимость", "plusvalore", "concept", ""),
    ("потребительная стоимость", "valore d'uso", "concept", ""),
    ("закон стоимости", "legge del valore", "concept", ""),
    ("заработная плата", "salario", "concept", ""),
    ("производительность труда", "produttività del lavoro", "concept", ""),
    ("необходимое общественное рабочее время", "tempo di lavoro socialmente necessario", "concept", ""),
    ("свободное время", "tempo libero", "concept", ""),
    ("частичный труд", "lavoro parziale", "concept", "Teilarbeit"),
    ("трудовая армия", "esercito del lavoro", "concept", ""),
    ("коллективный капиталист", "capitalista collettivo", "concept", "Engels"),
    ("господство капитала", "dominio del capitale", "concept", ""),
    ("капитал как общественное отношение", "il capitale come rapporto sociale", "concept", ""),
    ("историческая роль капитала", "missione storica del capitale", "concept", ""),
    ("историческая миссия", "missione storica", "concept", ""),
    ("автоматическая фабрика", "fabbrica automatica", "concept", "Marx"),
    ("кризис перепроизводства", "crisi di sovrapproduzione", "concept", ""),
    ("относительное обнищание", "impoverimento relativo", "concept", ""),
    ("абсолютная нищета", "miseria assoluta", "concept", ""),
    ("воспроизводство в расширенном масштабе", "riproduzione su scala allargata", "concept", ""),
    ("периферия и полупериферия", "periferia e semiperiferia", "concept", ""),
    ("эксплуатация человека человеком", "sfruttamento dell'uomo sull'uomo", "phrase", ""),
    ("денежно-товарные отношения", "rapporti monetario-mercantili", "concept", ""),
    ("товарно-денежные отношения", "rapporti monetario-mercantili", "concept", ""),
    ("прямое распределение", "distribuzione diretta", "concept", ""),
    ("натуральное хозяйство", "economia naturale", "concept", ""),
    ("потребительский кооператив", "cooperativa di consumo", "concept", ""),
    ("моральный и физический износ", "logorio morale e fisico", "concept", ""),
    ("экономический агент", "agente economico", "concept", ""),
    ("способ общения", "forma di relazioni", "concept", "Verkehrsform"),
    ("материальное производство", "produzione materiale", "concept", ""),
    ("непосредственное производство человека", "produzione immediata dell'uomo", "concept", ""),
    ("производство и воспроизводство непосредственной жизни", "produzione e riproduzione della vita immediata", "quote", "Engels"),
    ("производство средств к жизни", "produzione dei mezzi di sussistenza", "concept", ""),
    ("продолжение рода", "riproduzione della specie", "concept", ""),
    ("воспроизводство общественной жизни", "riproduzione della vita sociale", "concept", ""),
    ("идеальное", "ideale", "concept", "Il'enkov's category: l'ideale"),
    ("производство идеального", "produzione dell'ideale", "concept", ""),
    ("сфера идеального", "sfera dell'ideale", "concept", ""),
    ("надстроечная деятельность", "attività sovrastrutturale", "concept", ""),
    ("надстройка", "sovrastruttura", "concept", ""),
    ("базис", "base", "concept", "base e sovrastruttura"),
    ("локальный коммунизм", "comunismo locale", "concept", "author's coinage"),
    ("тотальный коммунизм", "comunismo totale", "concept", "author's coinage"),
    ("коммунизм по нужде", "comunismo per bisogno", "concept", "contrast with по внутренней необходимости"),
    ("коммунизм по внутренней необходимости", "comunismo per necessità interna", "concept", ""),
    ("коммунизм как наука", "comunismo come scienza", "concept", ""),
    ("научный коммунизм", "comunismo scientifico", "concept", ""),
    ("научный социализм", "socialismo scientifico", "concept", ""),
    ("первобытный коммунизм", "comunismo primitivo", "concept", ""),
    ("коммунистический идеал", "ideale comunista", "concept", ""),
    ("общественный идеал", "ideale sociale", "concept", ""),
    ("строительство коммунизма", "edificazione del comunismo", "concept", ""),
    ("социалистическое строительство", "edificazione socialista", "concept", ""),
    ("стихийное движение", "movimento spontaneo", "concept", "стихийный = spontaneo"),
    ("классовая позиция", "posizione di classe", "concept", ""),
    ("классовая борьба", "lotta di classe", "concept", ""),
    ("теоретическая борьба", "lotta teorica", "concept", ""),
    ("классовые противоположности", "antagonismi di classe", "concept", "Manifesto"),
    ("сословный принцип", "principio cetuale", "concept", ""),
    ("революционная теория", "teoria rivoluzionaria", "concept", ""),
    ("государство", "Stato", "concept", "capitalized for the political state"),
    ("отмирание государства", "estinzione dello Stato", "concept", "Engels/Lenin"),
    ("самоуничтожение государства", "autosoppressione dello Stato", "concept", ""),
    ("правовое государство", "Stato di diritto", "concept", ""),
    ("государственная машина", "macchina statale", "concept", ""),
    ("аппарат подавления", "apparato di repressione", "concept", ""),
    ("господствующий класс", "classe dominante", "concept", ""),
    ("правящий класс", "classe dominante", "concept", ""),
    ("чиновник", "funzionario", "concept", ""),
    ("самоуправление", "autogoverno", "concept", ""),
    ("органы общественного самоуправления", "organi di autogoverno sociale", "concept", ""),
    ("самоорганизация", "auto-organizzazione", "concept", ""),
    ("учёт и контроль", "calcolo e controllo", "quote", "Lenin, Stato e rivoluzione"),
    ("Вся власть советам", "Tutto il potere ai soviet", "phrase", ""),
    ("каждая кухарка должна научиться управлять государством", "ogni cuoca deve imparare a governare lo Stato", "quote", "Lenin"),
    ("кухарка", "cuoca", "concept", ""),
    ("в музей древностей, рядом с прялкой и с бронзовым топором", "nel museo delle antichità, accanto alla rocca e all'ascia di bronzo", "quote", "Engels"),
    ("взятие средств производства во владение государством от имени всего общества", "presa di possesso dei mezzi di produzione da parte dello Stato in nome della società", "quote", "Engels, Anti-Dühring"),
    ("свободное развитие каждого является условием свободного развития всех", "il libero sviluppo di ciascuno è condizione del libero sviluppo di tutti", "quote", "Manifesto"),
    ("коммунисты могут выразить свою теорию одним положением: уничтожение частной собственности", "i comunisti possono riassumere la loro teoria in questa unica espressione: abolizione della proprietà privata", "quote", "Manifesto"),
    ("Экспроприация земельной собственности и обращение земельной ренты на покрытие государственных расходов", "Espropriazione della proprietà fondiaria e impiego della rendita fondiaria per le spese dello Stato", "quote", "Manifesto, first measure"),
    ("энергический принцип ближайшего будущего", "principio energico del prossimo avvenire", "quote", "Manoscritti 1844"),
    ("свободная игра физических и умственных сил", "libero gioco delle forze fisiche e intellettuali", "quote", "Capitale I"),
    ("царство свободы", "regno della libertà", "quote", "Capitale III"),
    ("Мы не утописты", "Non siamo utopisti", "phrase", "Lenin"),
    ("любовь – теорема, которую нужно доказывать каждый день", "l'amore è un teorema che bisogna dimostrare ogni giorno", "quote", "Gorin"),
    ("Без революционной теории не может быть и революционного движения", "Senza teoria rivoluzionaria non vi può essere movimento rivoluzionario", "quote", "Lenin, Che fare?"),
    ("ум, честь и совесть нашей эпохи", "l'intelligenza, l'onore e la coscienza della nostra epoca", "quote", "Lenin"),
    ("Оружие критики не может, конечно, заменить критики оружием", "L'arma della critica non può certo sostituire la critica delle armi", "quote", "Marx"),
    ("материальная сила", "forza materiale", "concept", ""),
    ("каждый шаг действительного движения важнее дюжины программ", "ogni passo del movimento reale vale più di una dozzina di programmi", "quote", "Marx to Bracke"),
    ("Пролетарии всех стран, соединяйтесь!", "Proletari di tutti i paesi, unitevi!", "phrase", ""),
    ("подвиг Фейербаха", "la grande impresa di Feuerbach", "quote", "Manoscritti 1844"),
    ("земная основа", "base terrena", "concept", "Tesi su Feuerbach IV"),
    ("святое семейство", "sacra famiglia", "phrase", "Tesi su Feuerbach IV"),
    ("самоотчуждение", "autoalienazione", "concept", ""),
    ("отчуждение", "alienazione", "concept", "отчуждённый = alienato"),
    ("кулачное право", "diritto del pugno", "concept", "Faustrecht"),
    ("право сильного", "diritto del più forte", "concept", ""),
    ("оппортунизм", "opportunismo", "concept", ""),
    ("прудонизм", "proudhonismo", "concept", ""),
    ("теоретический смысл", "senso teorico", "concept", "Engels"),
    ("партийность", "spirito di partito", "concept", "Leninist partijnost'"),
    ("политическая экономия", "economia politica", "concept", ""),
    ("объективная истина", "verità oggettiva", "concept", ""),
    ("общечеловеческий", "universalmente umano", "concept", ""),
    ("целеполагание", "posizione di fini", "concept", "Zwecksetzung"),
    ("духовная культура", "cultura spirituale", "concept", ""),
    ("мир идей", "mondo delle idee", "concept", ""),
    ("профессиональный кретинизм", "cretinismo professionale", "concept", "Marx"),
    ("в конечном счёте", "in ultima istanza", "phrase", "Engels"),
    ("в конечном счете", "in ultima istanza", "phrase", ""),
    ("понятие", "concetto", "concept", "opposed to представление"),
    ("представление", "rappresentazione", "concept", "opposed to понятие"),
    ("мышление", "pensiero", "concept", ""),
    ("субъект мышления", "soggetto del pensiero", "concept", ""),
    ("субъект исторического действия", "soggetto dell'azione storica", "concept", ""),
    ("культура мышления", "cultura del pensiero", "concept", ""),
    ("диалектическое мышление", "pensiero dialettico", "concept", ""),
    ("чувственность", "sensibilità", "concept", ""),
    ("нравственность", "moralità", "concept", "not eticità"),
    ("научная картина мира", "immagine scientifica del mondo", "concept", ""),
    ("политехническое образование", "istruzione politecnica", "concept", ""),
    ("политехнизм", "politecnismo", "concept", ""),
    ("планирование", "pianificazione", "concept", ""),
    ("конкретно-исторический", "storico-concreto", "concept", ""),
    ("совместно-раздельная деятельность", "attività congiunta-separata", "concept", "quoted term of art"),
    ("быт", "vita quotidiana", "concept", "byt"),
    ("общественное питание", "ristorazione collettiva", "concept", ""),
    ("общепит", "ristorazione collettiva", "concept", ""),
    ("обыватель", "filisteo", "concept", ""),
    ("мещанский", "piccolo-borghese", "concept", ""),
    ("воспитание", "educazione", "concept", "воспитатель = educatore"),
    ("общественное воспитание", "educazione sociale", "concept", ""),
    ("коллектив", "collettivo", "concept", ""),
    ("первичный коллектив", "collettivo primario", "concept", "Makarenko"),
    ("трудовой коллектив", "collettivo di lavoro", "concept", ""),
    ("половая любовь", "amore sessuale", "concept", "Engels"),
    ("семейные ценности", "valori familiari", "concept", ""),
    ("коммуна", "comune", "concept", "feminine: la comune, le comuni"),
    ("свободное ПО", "software libero", "concept", ""),
    ("программное обеспечение", "software", "concept", ""),
    ("открытый код", "codice aperto", "concept", ""),
    ("открытое программное обеспечение", "software a codice aperto", "concept", ""),
    ("исходники", "sorgenti", "concept", ""),
    ("база данных", "database", "concept", ""),
    ("общедоступная база данных", "database ad accesso libero", "concept", ""),
    ("пространственная база данных", "database geospaziale", "concept", ""),
    ("информационная грамотность", "alfabetizzazione informatica", "concept", ""),
    ("компьютерная грамотность", "alfabetizzazione informatica", "concept", ""),
    ("общегосударственная система управления экономикой", "sistema statale di gestione dell'economia", "concept", "Gluškov's OGAS"),
]

# Inflectional endings that may follow a stem (nouns, adjectives, participles).
ENDINGS = sorted({
    "ями", "ами", "иями", "ого", "его", "ому", "ему", "ыми", "ими", "ых", "их", "ым", "им",
    "ой", "ей", "ою", "ею", "ом", "ем", "ём", "ах", "ях", "ам", "ям", "ов", "ев", "ёв",
    "ия", "ие", "ий", "ии", "ию", "ую", "юю", "ая", "яя", "ое", "ее", "ые", "ью",
    "а", "я", "ы", "и", "у", "ю", "е", "ё", "о", "ь", "й",
}, key=len, reverse=True)
MIN_STEM = 3
CYR_TOKEN = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")


def stem(word: str) -> str:
    """Strip the longest inflectional ending (final hyphen segment only)."""
    w = word.lower()
    head, sep, tail = w.rpartition("-")
    for e in ENDINGS:
        if tail.endswith(e) and len(tail) - len(e) >= MIN_STEM:
            tail = tail[: -len(e)]
            break
    return f"{head}{sep}{tail}" if sep else tail


def matches(token: str, term_word: str) -> bool:
    """True when `token` is an inflected form of `term_word`.

    Two candidate stems are tried: the word itself (surnames in -ов/-ин, words
    whose apparent ending is part of the stem) and the word minus its longest
    inflectional ending. ё and е are treated alike because the source text
    spells many words without ё.
    """
    t = token.lower().replace("ё", "е")
    w = term_word.lower().replace("ё", "е")
    for s in (w, stem(w)):
        if t.startswith(s):
            rest = t[len(s):]
            if rest == "" or rest in ENDINGS:
                return True
    return False


# Sources whose automatic stemming would catch unrelated words (быт -> быть/бытие,
# ПО -> по, Вася -> Вас, Капитал -> капитал ...): list their forms by hand.
EXACT: dict[str, list[str]] = {
    "быт": ["быт", "быта", "быту", "бытом", "быте"],
    "ПО": ["ПО"],
    "СССР": ["СССР"], "РФ": ["РФ"], "США": ["США"], "МОТ": ["МОТ"],
    "Вася": ["Вася", "Васи", "Васе", "Васю", "Васей"],
    "Петя": ["Петя", "Пети", "Пете", "Петю", "Петей"],
    "Капитал": ["Капитал", "Капитала", "Капиталу", "Капиталом", "Капитале"],
    "Манифест": ["Манифест", "Манифеста", "Манифесту", "Манифестом", "Манифесте"],
    "Рукописи": ["Рукописи", "Рукописей", "Рукописям", "Рукописях"],
    "Октябрь": ["Октябрь", "Октября", "Октябрю", "Октябрём", "Октябре"],
    "нэп": ["нэп", "нэпа", "нэпу", "нэпом", "нэпе", "НЭП", "НЭПа"],
    "идеальное": ["идеальное", "идеального", "идеальному", "идеальным", "идеальном"],
    "снятие": ["снятие", "снятия", "снятию", "снятием", "снятии"],
    "понятие": ["понятие", "понятия", "понятию", "понятием", "понятии", "понятий", "понятиям",
                "понятиями", "понятиях"],
    "представление": ["представление", "представления", "представлению", "представлением",
                      "представлении", "представлений", "представлениям", "представлениями", "представлениях"],
}
SENTENCE_PUNCT = re.compile(r"[.;!?]")


def corpus_variants(source: str, corpus: str, tokens: list[tuple[str, int, int]]) -> list[str]:
    if source in EXACT:
        return [v for v in EXACT[source] if v != source]
    words = CYR_TOKEN.findall(source)
    if not words or re.search(r"[A-Za-z0-9]", source):
        return []
    n = len(words)
    upper_only = source[0].isupper()
    found: dict[str, None] = {}
    for i in range(len(tokens) - n + 1):
        if not all(matches(tokens[i + k][0], words[k]) for k in range(n)):
            continue
        surface = re.sub(r"\s+", " ", corpus[tokens[i][1]: tokens[i + n - 1][2]])
        if upper_only and not surface[0].isupper():
            continue
        if n > 1 and (len(surface) > len(source) * 1.5 + 6 or
                      len(SENTENCE_PUNCT.findall(surface)) > len(SENTENCE_PUNCT.findall(source))):
            continue
        found[surface] = None
    return list(found)


HYPHEN_BREAK = re.compile(r"([А-Яа-яЁё])- ([а-яё])")
CYRILLIC_ROMAN = re.compile(r"(?<![А-Яа-яЁёA-Za-z])[ХІIXV]+(?![А-Яа-яЁёA-Za-z])")


def russian_corpus(parts_dir: Path) -> str:
    """Plain text of the Russian LaTeX parts, as parts_text_exchange.py exports it."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from parts_text_exchange import parse_latex_part, render_simple_text_part

    texts = []
    for path in sorted(parts_dir.glob("*.tex")):
        text = render_simple_text_part(parse_latex_part(path))
        text = HYPHEN_BREAK.sub(r"\1-\2", text)
        text = CYRILLIC_ROMAN.sub(lambda m: m.group(0).translate(str.maketrans("ХІ", "XI")), text)
        texts.append(text)
    return "\n\n".join(texts)


def main() -> None:
    ap = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    ap.add_argument("--corpus", type=Path, default=None,
                    help="directory of exported .txt parts (default: read russian/parts/*.tex)")
    ap.add_argument("--out", type=Path, default=here / "italiano" / "glossary.ru-it.json")
    args = ap.parse_args()

    if args.corpus:
        corpus = "\n\n".join(p.read_text(encoding="utf-8") for p in sorted(args.corpus.glob("*.txt")))
    else:
        corpus = russian_corpus(here / "russian" / "parts")
    tokens = [(m.group(0), m.start(), m.end()) for m in CYR_TOKEN.finditer(corpus)]

    seen: dict[str, dict] = {}
    unmatched: list[str] = []
    for source, target, category, note in ENTRIES:
        variants = corpus_variants(source, corpus, tokens)
        alts = [source] + [v for v in variants if v != source]
        key = "|".join(alts)
        if not variants and source not in corpus:
            unmatched.append(source)
        entry = {"source": key, "target": target, "category": category}
        if note:
            entry["_note"] = note
        seen[source] = entry

    glossary = {
        "name": "What is communism (ru -> it)",
        "_about": (
            "Glossary for the whole booklet, built by build_glossary.py: the chapter-03 glossary "
            "plus terms harvested from every chapter (names in the scientific transliteration used "
            "by Italian Wikipedia, established Italian titles, short canonical formulas of Marx, Engels "
            "and Lenin, the author's coinages, and the Marxist lexicon). Each source lists the inflected "
            "forms found in the Russian text, separated by '|', so TranslateBooksWithLLMs' per-chunk "
            "filter matches them. Use with: python translate.py ... --glossary glossary.ru-it.json"
        ),
        "terms": list(seen.values()),
    }
    args.out.write_text(json.dumps(glossary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total_alts = sum(len(t["source"].split("|")) for t in glossary["terms"])
    print(f"wrote {args.out}: {len(glossary['terms'])} terms, {total_alts} source forms")
    print(f"{len(unmatched)} sources without a literal occurrence in the corpus:")
    for s in unmatched:
        print(f"  - {s}")


if __name__ == "__main__":
    main()
