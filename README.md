Seminaarityön tavoitteena oli toteuttaa järjestelmä, joka pystyy käynnistämään ja sammuttamaan saunan automaattisesti HUUM-kontrollerin avulla. Järjestelmä lukee saunavaraukset ja osaa käynnistää saunan oikeaan aikaan ilman manuaalista ohjausta. Tarkoitus oli oppia API-kutsuja, Python-ohjelmointia sekä ajastettua automaatiota.

Toteutin pythonpohjaisern saunaohjaimen joka kommunikoi huum APIn kanssa. Järjestelmä pystyy tarkistamaan saunan tilan ja käynnistämään, sekä sammuttamaan saunan oikeaan aikaan iCAL kalentirin perusteella.

Arkkitehtuuri 
Main.py tarjoaa 
API reitit ja käyttöliittymän.

Chacker.py hakee kalenteri varauksia ja kertoo pitääkö sauna laittaa päälle vai sammuttaa varausten perusteella. 
Huum saunan tarjoamat api materiaalit on pyydetty suoraan kiukaan valmistajalta sähköpostilla ja niiden avulla mahdollista ohjata saunaa. Tällä hetkellä tämä projecti pyörii google cloud runissa.


Mitä opin 
Opin miten google cloudissa voi ajaa omia python ohjelmia esim google cloud run tai ajastetut jobit. 
Opin miten tehdään http ja api kutsuja ja miten iCAl kalenteridataa luetaan (alku ja loppuajat) käynnistyksiä varten.
Miten suunnitellaan käytännön ajastuslogiikka, jossa otetaan huomioon milloin kannattaa käynnistää ja milloin kannattaa sammuttaa.

Jatkokehitysideoita
Enemmän ominaisuuksia visuaaliseen käyttöliittymään ja parempi turvallisuus esim salasanoille paremmat paikat.


Lähteet
Huumin lähettämä API dokumentaatio.
ChatGPT:tä on hyödynnetty tämän kokonaisuuden suunnittelussa ja koodin toteutuksessa.
